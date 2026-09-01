---
name: doppler
description: >-
  Store, read, and wire up env-style secrets in Doppler — resolve the real project/config, emit
  copy-ready command templates, and keep plaintext values out of the transcript.
  TRIGGER when: a task touches secrets, API keys, tokens, passwords, or `.env` files; before
  suggesting where a key should live, handing the user a command that carries a secret value, or
  running any `doppler` command; or the user has a secret on their clipboard.
  DO NOT TRIGGER when: the secret is a whole document to commit encrypted (use `/transcrypt`), or the
  project already uses a different secret manager (Vault, a cloud secret manager) — respect it.
allowed-tools: Bash(command -v doppler:*), Bash(doppler:*), Bash(test:*), Bash(grep:*), Bash(printf:*), Bash(node:*), Bash(python:*), Read, Write, Edit
---

# Doppler (env-style secrets)

Doppler is the default store for every env-style secret — API keys, tokens, passwords, connection
strings — in place of a plaintext `.env`. One source of truth, synced across the user's Windows and
macOS machines, with nothing secret committed. The account's workplace is `sava`.

## Context
- Doppler CLI: !`command -v doppler >/dev/null 2>&1 && echo INSTALLED || echo MISSING`
- Existing projects: !`doppler projects --json 2>&1 | tr ',' '\n' | grep -o '"name":"[^"]*"' || echo UNAVAILABLE`
- Configs in this repo's project: !`doppler configs --json 2>&1 | tr ',' '\n' | grep -o '"name":"[^"]*"' || echo "UNBOUND — list with doppler configs -p <shard>"`
- This repo's doppler.yaml: !`test -f doppler.yaml && cat doppler.yaml || echo NONE`
- This directory's binding: !`doppler configure get project --plain 2>/dev/null | grep . || echo UNBOUND`

## 1. Resolve project and config — never guess them

Read the coordinates off **Existing projects** and **Configs in this repo's project** (Context) — a
coordinate is a project *and* a config, and under the shard rule the config carries the app's identity:

- The workplace name `sava` is **not** a project. Never `-p sava`.
- Doppler's sample project `example-project` is not one of the user's. Never write to it.
- **A new app gets a config, not a project.** The workplace is capped at **10 projects**, all ten are
  in use, and `doppler projects create` now fails with `Your workplace has reached its limit of 10
  projects`. Apps share a project — a *shard*, chosen by trust boundary — and take one config each:
  `dev_<app>` and `prd_<app>`. Reach for `prd_<app>` only when the task is genuinely
  production-facing, and say out loud that you did.
- **`dev`, `stg` and `prd` are root configs, and they stay permanently empty.** A branch config
  inherits its root's secrets *including values*, so anything left in `local/prd` is readable by every
  app sharing that environment, and a `-c prd` typed where `-c prd_<app>` was meant writes into the
  root and silently propagates that value to every co-resident app. Always name the full config.
- The nine projects that predate the shard rule — `claude-code-dashboard`, `greenmur`, `landlord`,
  `printlab`, `scheduler`, `tools`, `travel-map`, `trips`, `whats-next` — keep their existing
  `dev`/`prd` layout; live systems read those values and migrating them would be risk for no benefit.
  The shard rule governs new apps, and apps that move for some other reason.
- Two stores, and they don't mix:
  - **The app's own config inside a shard project** — `dev_<app>` / `prd_<app>`, the app name
    kebab-case after the env-slug prefix — secrets the app consumes at runtime. Shards are divided by
    trust boundary, by where the secret is materialized. `local` (workstation-only apps) is the only
    shard so far, because every app on the shared box predates the shard rule and keeps its own
    project — so **a new box-hosted app has no shard to join yet**. Creating one spends a project slot;
    raise it with the user rather than picking a home for it.
  - **`tools` / `prd`** — credentials *Claude* uses ad hoc across projects (Porkbun, Resend,
    Tailscale, Backblaze, `TRANSCRYPT_KEY`). The inventory lives in the `refs-private` memory. Read
    from it when a task needs a third-party credential; never copy one into an app's own config.
- If the repo has no config yet, see `references/project-setup.md` — it covers picking the shard and
  creating the branch config. Do not run `doppler projects create`; the cap is reached.

When **Existing projects** reads `UNAVAILABLE`, run `doppler projects` directly. An auth error there
means the user must run `doppler login` themselves in a real terminal — it is interactive, needs a
TTY, and fails under Claude Code's `!` prefix with "Incorrect function". If **Doppler CLI** is
`MISSING`, see `references/project-setup.md` for the per-OS install.

## 2. Always emit the command, never just describe it

Whenever you ask for, suggest, or explain storing a key, output the exact command in a fenced code
block — never prose alone, and never a blockquote (the terminal renders its `|` gutter into the paste
and corrupts it). Fill in every part you already know (the key name, `-p`, `-c`); mark only what the
user must supply with a `{{kebab-case-hint}}` placeholder, never a plausible-looking fake value.

The templates below write `-c <cfg>`. Substitute the app's own config — `dev_<app>` / `prd_<app>` in a
shard, or the legacy `dev` / `prd` in one of the nine pre-shard projects. Never leave a bare `dev`,
`stg` or `prd` in a shard command: those are root configs, every branch config inherits their values,
and the write is visible to every co-resident app.

Pick the template by who holds the value.

### Store a value only the user has

A dashboard-generated API key, a password they chose. There are two routes, and **both get offered,
every time** — never the template on its own.

**Lead with the clipboard, which Claude runs:** "copy the value and I'll pipe it into Doppler straight
from your clipboard — it never reaches the transcript." It costs the user a `Ctrl+C` instead of a
second terminal, and no plaintext ever occupies a command line. The command is in the next section.

**When they would rather do it themselves**, hand them:

```
doppler secrets set <KEY>="{{the-value}}" -p <proj> -c <cfg> --silent
```

Tell them to run it **in a terminal outside Claude Code** — not via the `!` prefix, which records the
full command text, secret included, in the session transcript. The `--silent` flag suppresses the
command's *output*, not a `!`-recorded input. Doppler's dashboard is an equally good alternative.

Always quote the value. An unquoted `&`, `$`, `!`, backtick, or space is eaten by the shell and
silently stores nothing, a truncation, or an empty string. Double quotes cover `& % ( )` and spaces;
switch to single quotes when the value may contain `$`, a backtick, `!`, or `"`.

### Store a value from the clipboard

Claude runs this. The value travels clipboard → pipe → Doppler, so it appears in no command line, no
transcript, and no shell history — the file route's guarantee, minus the file. Read the clipboard with
the platform's native reader:

| OS | Reader |
|---|---|
| Windows (Git Bash) | `cat /dev/clipboard` |
| macOS | `pbpaste` |
| Linux | `wl-paste -n` (Wayland) or `xclip -selection clipboard -o` (X11) |

Guard the write and pipe it in one command, which prints a length and nothing else:

```bash
V=$(cat /dev/clipboard | tr -d '\r')
case "$V" in
  "") echo "clipboard is empty — nothing stored" ;;
  {{expected-prefix}}*) printf '%s' "$V" | doppler secrets set <KEY> -p <proj> -c <cfg> --silent && echo "stored <KEY> — ${#V} chars" ;;
  *) echo "clipboard does not look like <KEY> (${#V} chars) — nothing stored" ;;
esac
unset V
```

**Never look at the clipboard to check it.** A bare `cat /dev/clipboard` puts the secret straight into
the transcript, which is the whole leak this route exists to avoid. The clipboard may flow only into a
pipe or into a variable that is never printed; everything you report is derived from it — a length, a
line count, a prefix match — never the value.

The guard is what stops the wrong clipboard (a password, a URL, yesterday's token) from reaching
Doppler, where a delete does not erase it from version history. Merge the last two arms when the key
has no recognizable prefix, but keep the empty check either way: an empty clipboard otherwise stores
an empty string with no error at all, and the app fails much later with a blank credential.

Two Windows traps that the `tr` and the choice of reader exist to dodge:

- The `$( )` wrapper strips a trailing `\n` but not a trailing `\r`, and anything copied out of a
  Windows app arrives CRLF-terminated — so without `tr -d '\r'` the stored secret carries an
  invisible trailing carriage return. Stripping also normalizes inner CRLF to LF, which is what a
  multi-line value such as a PEM key wants.
- Never read the clipboard through PowerShell. Piping `Get-Clipboard` appends a CRLF of its own *and*
  transliterates non-ASCII through the console codepage — `é` arrives as `e`. Git Bash's
  `/dev/clipboard` is byte-exact UTF-8.

### Store a value already on disk, or one you generated

Claude runs this. Pipe it, so the plaintext never reaches the command line, the transcript, or shell
history — Doppler documents stdin as its own recommended method:

```
printf '%s' "$(cat <path-to-the-file>)" | doppler secrets set <KEY> -p <proj> -c <cfg> --silent
```

The `$( )` wrapper strips the trailing newline a file almost always carries; a bare `< file` redirect
would store that newline as part of the value. To confirm the round trip without printing anything,
use the digest check in `references/project-setup.md`.

### Import an existing `.env`

```
doppler secrets upload .env -p <proj> -c <cfg>
```

Then delete the `.env` and confirm `.gitignore` covers it. Full wiring in
`references/project-setup.md`.

### Reuse one value across configs (secret reference)

When the same value belongs in more than one config (or project), store it **once** and point the
others at it — one source of truth, no drift, editing the origin propagates. One config holds the real
secret; the others hold a `${...}` reference Doppler resolves on read.

**Which config holds the real value: the production one** — `prd_<app>` in a shard, `prd` in one of the
nine pre-shard projects. Production is the source of truth; the dev config holds a `${prd_<app>.<KEY>}`
reference. A value that already lives in the dev config and is later needed in production gets **moved**,
not copied — write it to the production config, then replace the dev value with a reference. Copying
leaves two originals free to drift, and the one you'd edit by habit is the wrong one. (This is only for values that are
genuinely the same everywhere — third-party API keys. Anything that must differ per environment, above all
`SESSION_SECRET` and any admin password, gets its own value in each config and is never referenced across:
a shared session secret makes a dev-minted cookie valid in production.)

Migrating one key, without the value touching a command line:

```bash
printf '%s' "$(doppler secrets get <KEY> -p <proj> -c <dev-cfg> --plain)" | doppler secrets set <KEY> -p <proj> -c <prd-cfg> --silent
doppler secrets set <KEY> '${<prd-cfg>.<KEY>}' -p <proj> -c <dev-cfg> --silent
```

Verify by digest at each step rather than trusting the round trip — compare a hash prefix and a length before
and after, so a truncated or empty write can't pass as success.

Syntax, inside the value:
- Same project, another config: `${<config>.<KEY>}` — e.g. `${prd_<app>.GOOGLE_MAPS_EMBED_API_KEY}` in
  a shard, `${prd.GOOGLE_MAPS_EMBED_API_KEY}` in a pre-shard project.
- Another project: `${<project>.<config>.<KEY>}`.

**Single-quote** the value so the shell doesn't expand `${...}` to empty:

```
doppler secrets set <KEY>='${<prd-cfg>.<KEY>}' -p <proj> -c <dev-cfg> --silent
```

`doppler secrets get` / `doppler run` return the **resolved** value, so the consuming app is unchanged
(whoever fetches the referencing config must also have access to the referenced one). Confirm it
resolved without printing it — a literal `${...}` back means it did not:

```
V="$(doppler secrets get <KEY> -p <proj> -c <cfg> --plain)"; case "$V" in '${'*) echo UNRESOLVED;; *) echo "resolved (len ${#V})";; esac; unset V
```

To share a *whole* config rather than one value, Doppler's named **Config Inheritance** does it in one
step, but it's Team/Enterprise-only — a per-value reference works without it. Root-to-branch
inheritance is *not* that feature and is always on: every branch config already inherits its root's
secrets **and their values** on every plan, which is why roots are kept empty rather than used to share.

### Run something with the secrets injected

```
doppler run -p <proj> -c <cfg> -- <command>
```

This is the normal consumption path — the app reads `process.env` / `os.environ` and never sees a
file. Drop `-p`/`-c` only when **This repo's doppler.yaml** (Context) shows a `setup:` block *and*
**This directory's binding** is not `UNBOUND`. When the binding is `UNBOUND`, bind it once with
`doppler setup --no-interactive` rather than carrying explicit flags forever — a committed
`doppler.yaml` on its own does not bind anything.

### Check a value without printing it

Auto-mode's safety classifier blocks echoing a secret to stdout ("Credential Materialization"), and
it is right to. Derive a non-secret answer instead — the command prints only a boolean:

```
doppler run -p <proj> -c <cfg> -- node -e 'console.log((process.env.<KEY>||"").startsWith("{{expected-prefix}}"))'
```

To see which keys exist, with no values at all: `doppler secrets --only-names -p <proj> -c <cfg>`.

### Materialize a raw value

Only when a command genuinely needs the value as an argument — and then pipe it straight into the
consumer rather than echoing it:

```
doppler secrets get <KEY> -p <proj> -c <cfg> --plain
```

The `--visibility masked` flag does **not** redact CLI output: at set time the confirmation table
still prints the plaintext, and later reads still return it in the clear to an authorized CLI user.
Masked is a dashboard access attribute. Use `--silent` for no echo; combine both for no echo *and* a
dashboard-masked secret.

### Put a stored value on the clipboard — and leave a `cb` behind

The mirror image of the clipboard write, for when the user has to paste a secret into a web form or a
vendor dashboard. It reaches their clipboard without passing through the transcript. Use the helper
rather than redirecting by hand: it picks the right sink per OS and reports a label, a length and a
digest instead of the value.

```
V=$(doppler secrets get <KEY> -p <proj> -c <cfg> --plain)
bash ~/.claude/skills/doppler/scripts/to-clipboard.sh "<what it is, in the user's words>" "$V"
```

**Then write `scripts/cb.sh`, every single time.** A clipboard does not survive a session: the user
comes back to paste hours later, having copied three other things since, and the value is gone —
which has already cost a round trip. `cb` is the fix, the same shape as `deploy` and `publish`:

```bash
#!/bin/bash
# Re-copy the value Claude last put on the clipboard. Run it as `cb`, from anywhere in this repo.
#
# Regenerated on every copy, so it always carries the most recent one — per-machine, gitignored, never committed.
# The value is fetched rather than stored here: a secret must not sit in plaintext on disk, and re-reading its
# source also means this keeps working after the secret is rotated.
#
# WHAT: <one line naming the value and where it gets pasted>
set -euo pipefail

value=$(doppler secrets get <KEY> -p <proj> -c <cfg> --plain)
bash ~/.claude/skills/doppler/scripts/to-clipboard.sh "<label>" "$value"
```

Rules for it:

- **Fetch, never embed.** The script holds the command that *retrieves* the value, so no plaintext
  secret lands on disk and a later rotation doesn't leave `cb` handing over a dead credential. A
  literal is acceptable only for something that isn't secret and has no source to re-read (a computed
  URL, an id); never for a token, key or password. If a secret has no reproducible source, put it in
  Doppler first — then it has one.
- **Overwrite it.** One value at a time, the most recent. `cb` means "give me back what you just
  copied", so a script that accumulates a menu of past values defeats the point.
- **Say it exists.** When handing over a clipboard value, tell the user `cb` will restore it — that is
  the whole reason the file is there.

`cb() { run_repo_script scripts/cb.sh "$@"; }` lives in the shell rc beside `deploy` and `publish`, and
`scripts/cb.sh` is covered by the per-machine wrapper block in the global excludes file. Both are
installed on this machine; on a fresh one, add them the same way the deploy skill adds its own.

To confirm the clipboard still holds what you put there, compare digests — never `cat` it.

### Delete a key

```
doppler secrets delete <KEY> -p <proj> -c <cfg> -y --silent
```

Without `--silent`, `delete` prints the whole *remaining* secrets table — every value — a transcript
leak. The `doppler-guard` PreToolUse hook now blocks a `set`/`delete` that omits `--silent`.

## 3. Landmines

- **A branch config inherits its root's secrets, values included.** Verified with a marker secret: set
  something in `local/prd` and every `prd_*` config in that project returns it. So a `-c prd` typed
  where `-c prd_<app>` was meant does not fail — it writes into the root and hands that value to every
  co-resident app, silently. Roots (`dev`, `stg`, `prd`) stay permanently empty, and every command
  names the full branch config.
- **A branch config's name must start with its environment slug and an underscore.**
  `doppler configs create transcripts -p local` is rejected; `doppler configs create prd_transcripts
  -p local` succeeds. The prefix is Doppler's rule, not a house style.
- **The project cap is 10 and it is reached.** `doppler projects create` fails with `Your workplace has
  reached its limit of 10 projects`; the cheapest plan that raises it is Team, $21/user/month. The free
  plan's other limits are not binding — 4 environments per project, 10 configs per environment
  *including* the root (so 9 branch configs), 1,200 secrets per config. Doppler also auto-creates a
  `dev_personal` branch config in every project, which eats one dev slot.
- **`doppler secrets set`/`delete` print the whole secrets table — every value — unless `--silent`.**
  Omitting it on a one-secret op dumps the entire config into the transcript (a real leak); the
  `doppler-guard` PreToolUse hook now hard-blocks a `set`/`delete` missing `--silent`.
- **The clipboard is shared, volatile state.** Another Claude session, another app, or the user's own
  next copy can replace it between two tool calls — observed within a single session while this route
  was being written. Read it in the same command that writes to Doppler; never capture it in one turn
  and use it in the next, and never stash it in a file "to restore later".
- **Windows Git Bash mangles path-like values.** MSYS rewrites any argument that *starts* like a
  POSIX path, so `doppler secrets set UPLOAD_DIR='/data/uploads'` stores
  `C:/Program Files/Git/data/uploads`. Piping via stdin dodges the conversion entirely — one more
  reason it is the default. See `~/.claude/learnings/docker-windows-git-bash.md`.
- **A committed `doppler.yaml` does not bind the directory.** Without a one-time
  `doppler setup --no-interactive`, `doppler run` fails with `You must specify a project` — which
  reads like a missing secret rather than missing setup.
- **With `doppler run`, a `dotenv` import is redundant** and re-introduces a second source of truth.
  See `~/.claude/learnings/nextjs16-prisma7-scaffold.md`.
- **`deploy` and `publish` need different configs.** Never let one command reach both.
- **Offer, don't impose.** If a project already has Vault, a cloud secret manager, or
  encrypted-in-repo secrets, respect it rather than swapping to Doppler.

## Out of scope

- Do **not** commit a secret value anywhere — `doppler.yaml` and any config template hold coordinates
  and placeholders only.
- Do **not** hand the user a `!`-prefixed command carrying a plaintext value.
- Do **not** put env-style credentials in a committed file — `/transcrypt` protects *documents*, not keys.
- Do **not** restate the deploy flow. Rendering secrets into a runtime config
  (`doppler secrets substitute`) belongs to `/deploy`.
- Do **not** work around a classifier denial by printing a secret another way — derive a boolean, or
  ask the user to approve.

## Related

- `references/project-setup.md` — new project, `doppler.yaml`, directory binding, npm scripts,
  second-machine onboarding, migrating a value that already sits on disk.
- `references/troubleshooting.md` — error → cause → fix.
- The `refs-private` memory — inventory of the `tools` / `prd` ad-hoc credential store.
- The `/transcrypt` skill — retrieves the shared `TRANSCRYPT_KEY` from that store.
- The `/deploy` skill — renders a secret-bearing runtime config at deploy time.
