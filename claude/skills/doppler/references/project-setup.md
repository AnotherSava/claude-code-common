# Wiring a project onto Doppler

Consult this when a repo has no Doppler config yet, when a second machine needs access, or when a
secret that already sits on disk has to move into Doppler.

## Install the CLI

- **Windows:** `winget install Doppler.doppler`
- **macOS:** `brew install gnupg` (Doppler's binaries are signature-verified), then
  `brew install dopplerhq/cli/doppler` — Doppler's own tap, which supports `doppler update`. The
  Homebrew core formula `doppler` also exists but is not the documented path.

## Create the config

**Do not run `doppler projects create`.** The workplace is capped at **10 projects**, all ten are in
use, and the command now fails with `Your workplace has reached its limit of 10 projects`. Raising the
cap means the Team plan at $21/user/month. A new app therefore gets a *config* inside a shard project
it shares with other apps — the axis with room, since each project allows 4 environments × 10 configs.

1. Pick the shard by trust boundary — by where the secret is materialized. `local` holds
   workstation-only apps; a repo that predates the shard rule keeps its own project; `tools` is
   Claude's ad-hoc cross-project credential store, not a home for an app's runtime secrets. List what
   is already there, so the name is free and the shard still has room:

   ```
   doppler configs -p <shard>
   ```

2. Create one config per environment the app actually needs. **The name must start with the
   environment slug and an underscore** — `doppler configs create transcripts` is rejected,
   `prd_transcripts` succeeds — and the rest is the app name, kebab-case, matching the repo:

   ```
   doppler configs create prd_<app-name> -p <shard>
   doppler configs create dev_<app-name> -p <shard>
   ```

   The roots `dev`, `stg` and `prd` already exist from when the project was created. **Leave them
   permanently empty**: a branch config inherits its root's secrets *including values*, so anything in
   a root is readable by every app in the shard. Budget 9 branch configs per environment — 10 minus
   the root — and one dev slot is already gone to the `dev_personal` config Doppler auto-creates.

3. Add the secrets with the templates in SKILL.md § 2, or import an existing file:

   ```
   doppler secrets upload .env -p <shard> -c dev_<app-name>
   ```

   Then delete the `.env` and make sure `.gitignore` covers it. `doppler secrets upload` also accepts
   a JSON file.

## Commit a `doppler.yaml`

It holds coordinates, never values, so it is safe to commit and it lets every other machine resolve
the project without `-p`/`-c`:

```yaml
setup:
  project: <shard>
  config: dev_<app-name>
```

## Bind the directory (the step that is easy to miss)

The committed `doppler.yaml` alone does **not** make `doppler run` work — the directory has to be
bound once per machine, or every command fails with `You must specify a project` /
`The fallback file does not exist`. Claude can run this itself; it reads project and config straight
out of `doppler.yaml` and needs no TTY:

```
doppler setup --no-interactive
```

## Wrap the scripts that need secrets

Wrap only the env-dependent ones — `dev`, `db:migrate`, `db:seed`:

```json
"dev": "doppler run -- next dev",
"db:migrate": "doppler run -- prisma migrate deploy"
```

Leave `build`, `start`, `test`, and `lint` bare so CI and production aren't forced through Doppler.
Once every script that reads a secret goes through `doppler run`, drop any `dotenv` import and the
`dotenv` devDependency — the vars are already in `process.env`, and keeping both re-creates the
two-sources-of-truth problem Doppler was adopted to end. The trade-off is deliberate: running the
tool raw then fails fast with the var undefined instead of silently reading a stale `.env`.

## Second-machine onboarding

Three steps, and the middle one is the user's:

1. Install the CLI (above).
2. **The user runs `doppler login`** in a real terminal. It is interactive, needs a TTY, and fails
   under Claude Code's `!` prefix with "Incorrect function". Do not try to drive it.
3. Claude runs `doppler setup --no-interactive` in the repo.

## Migrate a secret that already sits on disk

Never paste the value into a command. Pipe it, so it stays out of the command text, the transcript,
and shell history:

```
printf '%s' "$(cat <path-to-the-file>)" | doppler secrets set <KEY> -p <proj> -c <cfg> --silent
```

Verify the round trip without printing anything — this prints three booleans and nothing else:

```bash
doppler run -p <proj> -c <cfg> -- python <<'EOF'
import hashlib, os, pathlib

stored = os.environ["<KEY>"]
original = pathlib.Path("<path-to-the-file>").read_text().rstrip("\n")
print("same length:", len(stored) == len(original))
print("same sha256:", hashlib.sha256(stored.encode()).hexdigest() == hashlib.sha256(original.encode()).hexdigest())
print("no stray whitespace:", stored == stored.strip())
EOF
```

All three `True` means the value is safe to delete from disk.
