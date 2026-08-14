---
name: doppler
description: >-
  Store, read, and wire up env-style secrets in Doppler — resolve the real project/config, emit
  copy-ready command templates, and keep plaintext values out of the transcript.
  TRIGGER when: a task touches secrets, API keys, tokens, passwords, or `.env` files; before
  suggesting where a key should live, handing the user a command that carries a secret value, or
  running any `doppler` command.
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
- This repo's doppler.yaml: !`test -f doppler.yaml && cat doppler.yaml || echo NONE`
- This directory's binding: !`doppler configure get project --plain 2>/dev/null | grep . || echo UNBOUND`

## 1. Resolve project and config — never guess them

Read the coordinates off **Existing projects** (Context), which is the authoritative list:

- The workplace name `sava` is **not** a project. Never `-p sava`.
- Doppler's sample project `example-project` is not one of the user's. Never write to it.
- The config is **`dev`**. New projects get `dev`/`stg`/`prd`, but secrets, `doppler run`, and
  `doppler setup` all live in `dev`. Reach for `prd` only when the task is genuinely
  production-facing, and say out loud that you did.
- Two stores, and they don't mix:
  - **A per-app project**, kebab-case, named after the repo — secrets the app consumes at runtime.
  - **`tools` / `prd`** — credentials *Claude* uses ad hoc across projects (Porkbun, Resend,
    Tailscale, `TRANSCRYPT_KEY`). The inventory lives in the `refs-private` memory. Read from it when
    a task needs a third-party credential; never copy one into a per-app project.
- If the repo needs a project that doesn't exist yet, see `references/project-setup.md`.

When **Existing projects** reads `UNAVAILABLE`, run `doppler projects` directly. An auth error there
means the user must run `doppler login` themselves in a real terminal — it is interactive, needs a
TTY, and fails under Claude Code's `!` prefix with "Incorrect function". If **Doppler CLI** is
`MISSING`, see `references/project-setup.md` for the per-OS install.

## 2. Always emit the command, never just describe it

Whenever you ask for, suggest, or explain storing a key, output the exact command in a fenced code
block — never prose alone, and never a blockquote (the terminal renders its `|` gutter into the paste
and corrupts it). Fill in every part you already know (the key name, `-p`, `-c`); mark only what the
user must supply with a `{{kebab-case-hint}}` placeholder, never a plausible-looking fake value.

Pick the template by who holds the value.

### Store a value only the user has

A dashboard-generated API key, a password they chose. Hand them:

```
doppler secrets set <KEY>="{{the-value}}" -p <proj> -c dev --silent
```

Tell them to run it **in a terminal outside Claude Code** — not via the `!` prefix, which records the
full command text, secret included, in the session transcript. The `--silent` flag suppresses the
command's *output*, not a `!`-recorded input. Doppler's dashboard is an equally good alternative.

Always quote the value. An unquoted `&`, `$`, `!`, backtick, or space is eaten by the shell and
silently stores nothing, a truncation, or an empty string. Double quotes cover `& % ( )` and spaces;
switch to single quotes when the value may contain `$`, a backtick, `!`, or `"`.

### Store a value already on disk, or one you generated

Claude runs this. Pipe it, so the plaintext never reaches the command line, the transcript, or shell
history — Doppler documents stdin as its own recommended method:

```
printf '%s' "$(cat <path-to-the-file>)" | doppler secrets set <KEY> -p <proj> -c dev --silent
```

The `$( )` wrapper strips the trailing newline a file almost always carries; a bare `< file` redirect
would store that newline as part of the value. To confirm the round trip without printing anything,
use the digest check in `references/project-setup.md`.

### Import an existing `.env`

```
doppler secrets upload .env -p <proj> -c dev
```

Then delete the `.env` and confirm `.gitignore` covers it. Full wiring in
`references/project-setup.md`.

### Reuse one value across configs (secret reference)

When the same value belongs in more than one config (or project), store it **once** and point the
others at it — one source of truth, no drift, editing the origin propagates. One config holds the real
secret; the others hold a `${...}` reference Doppler resolves on read.

Syntax, inside the value:
- Same project, another config: `${<config>.<KEY>}` — e.g. `${prd.GOOGLE_MAPS_EMBED_API_KEY}`.
- Another project: `${<project>.<config>.<KEY>}`.

**Single-quote** the value so the shell doesn't expand `${...}` to empty:

```
doppler secrets set <KEY>='${prd.<KEY>}' -p <proj> -c dev --silent
```

`doppler secrets get` / `doppler run` return the **resolved** value, so the consuming app is unchanged
(whoever fetches the referencing config must also have access to the referenced one). Confirm it
resolved without printing it — a literal `${...}` back means it did not:

```
V="$(doppler secrets get <KEY> -p <proj> -c dev --plain)"; case "$V" in '${'*) echo UNRESOLVED;; *) echo "resolved (len ${#V})";; esac; unset V
```

To share a *whole* config rather than one value, Doppler's **Config Inheritance** does it in one step,
but it's Team/Enterprise-only — a per-value reference works without it.

### Run something with the secrets injected

```
doppler run -p <proj> -c dev -- <command>
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
doppler run -p <proj> -c dev -- node -e 'console.log((process.env.<KEY>||"").startsWith("{{expected-prefix}}"))'
```

To see which keys exist, with no values at all: `doppler secrets --only-names -p <proj> -c dev`.

### Materialize a raw value

Only when a command genuinely needs the value as an argument — and then pipe it straight into the
consumer rather than echoing it:

```
doppler secrets get <KEY> -p <proj> -c dev --plain
```

The `--visibility masked` flag does **not** redact CLI output: at set time the confirmation table
still prints the plaintext, and later reads still return it in the clear to an authorized CLI user.
Masked is a dashboard access attribute. Use `--silent` for no echo; combine both for no echo *and* a
dashboard-masked secret.

### Delete a key

```
doppler secrets delete <KEY> -p <proj> -c dev -y --silent
```

Without `--silent`, `delete` prints the whole *remaining* secrets table — every value — a transcript
leak. The `doppler-guard` PreToolUse hook now blocks a `set`/`delete` that omits `--silent`.

## 3. Landmines

- **`doppler secrets set`/`delete` print the whole secrets table — every value — unless `--silent`.**
  Omitting it on a one-secret op dumps the entire config into the transcript (a real leak); the
  `doppler-guard` PreToolUse hook now hard-blocks a `set`/`delete` missing `--silent`.
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
