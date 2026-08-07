---
name: feedback_doppler_secrets
description: Default to Doppler (not plaintext .env) for managing secrets/keys/tokens in any project
metadata:
  type: feedback
---

When a project needs secrets, API keys, or tokens, default to managing them in **Doppler** rather than a plaintext `.env`. The user has the Doppler CLI installed (`winget install Doppler.doppler`) and an account in workplace `sava`.

## Gotchas — verify against this file before writing config or a command (added 2026-08-05 after a session that guessed every one of these wrong)
- **`sava` is the *workplace*, not a project.** `doppler projects` lists the real, per-app projects; create/verify a kebab-case one named after the repo (e.g. `travel-map`). Never `-p sava`.
- **Default config is `dev`, not `prd`.** New projects get `dev`/`stg`/`prd`, but secrets and `doppler run`/`doppler setup` live in `dev`.
- **Set with `doppler secrets set KEY="value" -p <proj> -c dev --silent`** — always **quote the value** (generated passphrases contain `& % $ ! space` that break unquoted); `--silent`/masked nuance below.
- **Hand a secret `set` command to a *separate terminal* (or the dashboard) — never Claude's `!` prefix.** `!` records the command, value included, in the session transcript/logs (observed 2026-08-05: a passphrase set via `!` leaked twice, even with `--silent`, which hides output not the `!` input). A separate terminal keeps it off-transcript.
- **Commit a `doppler.yaml`** so `doppler run --` and second-machine `doppler setup` resolve project/config without `-p/-c`.
- The one-line pointer in `CLAUDE.md` is a pointer, **not** the answer — open this file and read the specifics before acting on the summary.

**Why:** The user wants secrets synced across multiple dev machines without committing them and without manual copy-paste drift. Doppler is the single source of truth; a plaintext `.env` per machine drifts and risks accidental commits. (Established 2026-06-23 while wiring a project's Doppler setup.)

**How to apply:**
- Per project: create a Doppler project + `dev` config, import any existing `.env` (`doppler secrets upload .env -p <proj> -c dev`), add a committable `doppler.yaml` (`setup:\n  project: <proj>\n  config: dev`) — it holds no secrets — and wrap the env-dependent dev scripts with `doppler run -- …` (e.g. `dev`, `db:migrate`). Leave `build`/`start`/`test`/`lint` bare so CI and prod aren't forced onto Doppler.
- Add/change a secret with `doppler secrets set KEY="value" -p <proj> -c dev` — **always quote the value**, never edit `.env`. Randomly generated passphrases routinely contain shell metacharacters (`&`, `%`, spaces, `!`, `$`) that, unquoted, trigger job control / word-splitting / history expansion and silently set a wrong, partial, or empty value (observed 2026-08-05: an unquoted `&`-containing passphrase set *nothing*; a `KEY="value"` retry worked). Double quotes cover `& % ( ) space`; if the value may contain `$`, a backtick, `!`, or `"`, use single quotes `'value'` (they suppress all expansion). Most robust: keep the secret off the command line entirely — pipe from stdin or set it in the Doppler dashboard (a CLI value also lands in shell history and in a Claude `!` transcript). To keep the plaintext value out of the terminal/scrollback when setting (or when handing the user a `set` command to run), use `--silent` — it suppresses all output (verified; rely on the exit code for success). **`--visibility masked` does NOT redact CLI output**: at set time the confirmation table still prints the plaintext value, and later `doppler secrets`/`doppler secrets get --plain` reads still return it in the clear to an authorized CLI user — masked is a Doppler dashboard/access attribute, not output redaction (verified 2026-07-25). There is no "masked confirmation table" mode: masked shows plaintext, `--silent` shows nothing. Combine `--silent --visibility masked` if you want no echo AND a masked-in-dashboard secret.
- Second-machine onboarding: `winget install Doppler.doppler` → `doppler login` (interactive — needs a real TTY; fails under Claude Code's `!` prefix with "Incorrect function") → `doppler setup` (auto-reads `doppler.yaml`).
- Offer, don't impose: if a project already has its own secret-management (Vault, cloud secret manager, encrypted-in-repo), respect it rather than swapping to Doppler.
- Reading a secret's value in an agent/auto-mode session: the safety classifier blocks echoing a secret to stdout (`doppler secrets get KEY --plain` → "Credential Materialization"). To *check* a value without printing it, derive a non-secret answer instead — `doppler run -- node -e 'console.log((process.env.DATABASE_URL||"").endsWith("dev.db"))'` prints only a boolean. Materialize the raw value only when a command genuinely needs it as an argument, and pipe it straight into the consumer rather than echoing it.
