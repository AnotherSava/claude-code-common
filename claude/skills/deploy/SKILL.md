---
name: deploy
description: Configure and run the LOCAL deploy — install the app on this machine or start its dev server — verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-intellij-plugin.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-dev-server.sh), Bash(bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh:*), Bash(bash scripts/deploy.sh), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Read(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Edit(~/.zshrc), Read(~/.zshrc)
---

**Scope — `deploy` is local only.** It makes the current code runnable *on this machine*: it
installs the built app locally (Tauri / IntelliJ plugin / .NET) or starts the project's local
server. It never ships anywhere public. Shipping outward is a different verb:

| Means | Where it lives |
| --- | --- |
| Run it *here*, on this machine | this skill |
| Cut a version: tag → CI → GitHub Release | the `release` skill |
| Ship a site to a public host | the project's own CI (e.g. a GitHub Actions workflow) |

Publishing to a host is deliberately **not** a skill. Publishing from a developer's working tree
lets the wrong environment's credentials, or uncommitted work, reach production silently — CI
builds a clean checkout with one pinned configuration and removes that whole failure class. A
project having both a local `deploy` and a publish pipeline is normal and not a conflict.

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Deploy function in shell rc: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "deploy()" || echo 0`
- run_repo_script helper in shell rc: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "run_repo_script()" || echo 0`
- Shell rc target: !`case "$(uname -s)" in Darwin) echo "~/.zshrc" ;; MINGW*|MSYS*|CYGWIN*) echo "~/.bashrc" ;; *) [ -n "$ZSH_VERSION" ] || [ "${SHELL##*/}" = "zsh" ] && echo "~/.zshrc" || echo "~/.bashrc" ;; esac`
- Wrapper script exists: !`test -f scripts/deploy.sh && echo yes || echo no`
- Wrapper target: !`grep -oE 'deploy(-[a-z]+)?\.sh' scripts/deploy.sh 2>/dev/null | tail -1 || echo none`
- Static web entry (index.html): !`(ls index.html web/index.html public/index.html src/index.html dist/index.html 2>/dev/null | grep -q .) && echo yes || echo no`
- Static web dir (dir holding index.html; empty if none): !`for d in . web public src dist; do [ -f "$d/index.html" ] && { echo "$d"; break; }; done; true`
- Project start script (a committed scripts/dev.sh the project already provides): !`test -f scripts/dev.sh && echo yes || echo no`
- Dev-server configured: !`grep -c '^DEPLOY_TYPE=dev-server' config/deploy.env 2>/dev/null || echo 0`
- Dev-server dir (package.json with a 'dev' script; empty if none): !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] && node -e "p=require('./'+process.argv[1]+'/package.json');process.exit(p.scripts&&p.scripts.dev?0:1)" "$d" 2>/dev/null && { echo "$d"; break; }; done; true`
- Dev-server start command guess: !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] || continue; node -e "p=require('./'+process.argv[1]+'/package.json');process.exit(p.scripts&&p.scripts.dev?0:1)" "$d" 2>/dev/null || continue; if [ -f "$d/pnpm-lock.yaml" ]; then echo "pnpm dev"; elif [ -f "$d/yarn.lock" ]; then echo "yarn dev"; elif [ -f "$d/bun.lockb" ]; then echo "bun run dev"; else echo "npm run dev"; fi; break; done; true`
- Dev-server port guess (from the dev script; empty if none found): !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] || continue; node -e "p=require('./'+process.argv[1]+'/package.json');s=(p.scripts&&p.scripts.dev)||'';m=s.match(/(?:-p|--port[= ])\s*(\d{2,5})/);if(m)console.log(m[1]);process.exit(s?0:1)" "$d" 2>/dev/null && break; done; true`
- Repo folder name: !`basename "$(pwd)"`
- Production branch: !`git symbolic-ref --short HEAD 2>/dev/null || echo main`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`
- Deploy env has CONFIG_DEST: !`grep -c '^CONFIG_DEST=' config/deploy.env 2>/dev/null || echo 0`
- Tauri project: !`test -f src-tauri/tauri.conf.json && echo yes || echo no`
- Tauri identifier: !`sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' src-tauri/tauri.conf.json 2>/dev/null | head -1 || echo none`
- Secret config template present (config/local.template.json): !`test -f config/local.template.json && echo yes || echo no`
- Deploy env has DOPPLER_PROJECT: !`grep -c '^DOPPLER_PROJECT=' config/deploy.env 2>/dev/null || echo 0`
- Doppler CLI available: !`command -v doppler >/dev/null 2>&1 && echo yes || echo no`
- Wrapper renders secrets via Doppler: !`grep -q 'doppler secrets substitute' scripts/deploy.sh 2>/dev/null && echo yes || echo no`
- .NET project: !`ls src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ plugin project: !`(test -f build.gradle.kts || test -f build.gradle) && grep -lE 'org\.jetbrains\.intellij(\.platform)?' build.gradle.kts build.gradle 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ target type: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh type 2>/dev/null || echo unknown`
- IntelliJ plugins-dir guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh plugins-dir 2>/dev/null || echo`
- IntelliJ IDE exe guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-exe 2>/dev/null || echo`
- IntelliJ IDE process guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-process 2>/dev/null || echo`
- Deploy env has IDE_PROCESS: !`grep -c '^IDE_PROCESS=' config/deploy.env 2>/dev/null || echo 0`
- Deploy env has IDE_EXE: !`grep -c '^IDE_EXE=' config/deploy.env 2>/dev/null || echo 0`

## 1. Detect project type

Pick the matching underlying deploy script based on the **Context** flags. Already-configured markers win first (a prior run picked the type):

- **Dev-server configured** ≥ 1 (`config/deploy.env` marks `DEPLOY_TYPE=dev-server`) → `TARGET=deploy-dev-server.sh`
- else **Tauri project** is yes → `TARGET=deploy-tauri.sh`
- else **IntelliJ plugin project** is yes → `TARGET=deploy-intellij-plugin.sh`
- else **.NET project** is yes → `TARGET=deploy.sh`
- else **Dev-server dir** is non-empty (a `package.json` with a `dev` script — Next.js, Remix, SvelteKit, Vite, a plain Node server) → `TARGET=deploy-dev-server.sh` (§2a)
- else **Static web entry (index.html)** is yes (a static site with no `dev` script — plain HTML/JS served from a directory) → `TARGET=deploy-dev-server.sh` (§2a), configured as a static file server
- else → **STOP**. Tell the user:
  > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`), IntelliJ plugins (`build.gradle[.kts]` using `org.jetbrains.intellij[.platform]`), .NET (`src/*.csproj`), and local web servers (a `package.json` with a `dev` script, or a static `index.html`). None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.
  >
  > If you meant to ship this somewhere public, that isn't `deploy`: a site goes live through the project's CI pipeline, and a versioned artifact through the `release` skill.

  Do not create `config/deploy.env` or the wrapper. Exit.

A project that also ships to a public host is not a conflict — `deploy` configures the local
side only, and CI handles shipping. Never ask the user to choose between the two. If
more than one *local* target's flag is yes (mixed repo), ask which one `deploy` should mean —
do not guess.

## 2. Check prerequisites

1. If **Deploy function in shell rc** is 0, append the `deploy` wrapper to the file in **Shell rc target** (i.e. `~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux-bash). It delegates to the shared `run_repo_script` helper, which walks up from the current directory to the repo's `scripts/deploy.sh` and runs it from the directory that holds it — so `deploy` works from any subdirectory (the underlying scripts read `config/deploy.env` relative to that root). If **run_repo_script helper in shell rc** is 0, append the helper too (the `build` skill installs the same one — add it only when missing, so it isn't duplicated):
   ```bash
   run_repo_script() { local rel="$1"; shift; local d="$PWD"; while [ "$d" != "/" ] && [ ! -f "$d/$rel" ]; do d="$(dirname "$d")"; done; if [ -f "$d/$rel" ]; then ( cd "$d" && bash "$rel" "$@" ); else echo "No $rel in this directory or any parent"; fi; }
   deploy() { run_repo_script scripts/deploy.sh "$@"; }
   ```

**If `TARGET` is `deploy-dev-server.sh`, configure via §2a and skip items 2–4. (Items 2–4 are for the local-install targets.)**

### 2a. Local web server configuration

For a local web server, `deploy` stops whatever holds the port and relaunches the start command detached (so it outlives the Claude session), then waits for the port to come up. Write `config/deploy.env` with these keys (ask only for keys not already present; use the Context-derived defaults — confirm them with the user rather than asking blind):

- `DEPLOY_TYPE=dev-server` — always write this; it's the marker that routes future runs straight to this target.
- `DEV_DIR=` — the directory `DEV_CMD` is **run from** (not necessarily the one being served), relative to repo root; logs are written here too. Decide it together with `DEV_CMD` below:
  - using the project's own `scripts/dev.sh` → `.`, since that path is repo-root-relative and the script decides for itself what to serve. Setting this to the web dir instead makes the command not found.
  - using a package-manager `dev` script → the **Dev-server dir** Context value (`.` for a root app, `web` for a monorepo subdir).
  - serving a static directory directly → the **Static web dir** value.
- `DEV_PORT=` — port the server listens on (used to stop the old instance and health-check the new one). Default = **Dev-server port guess** Context value if non-empty, else `3000` (note: Vite defaults to `5173`). Confirm with the user — the guess only catches ports written explicitly in the dev script. **If the project pins its port for an external reason** (an API key restricted to `http://localhost:<port>`, an OAuth redirect URI, a CORS allowlist), use that port and say so in the config comment — a "sensible" default silently breaks those.
- `DEV_CMD=` — command that starts the server. Derive the default:
  - if **Project start script** is yes → `bash scripts/dev.sh` — prefer the project's own committed starter, which may do setup the skill can't know about (rendering a gitignored config, fetching a token). It runs in the foreground and this target detaches it, which is the right shape.
  - else if **Dev-server dir** is non-empty → **Dev-server start command guess** Context value (picks `pnpm`/`yarn`/`bun`/`npm` from the lockfile). Keep it as the package-manager script (e.g. `npm run dev`) even when that script itself wraps another tool (Doppler, env loaders) — the wrapping lives in `package.json`, not here.
  - else (static site, no `dev` script) → `python -m http.server <DEV_PORT> --directory <DEV_DIR>`

`config/deploy.env` holds no secrets, so it is safe to commit (and committing it gives every contributor the same `! deploy`). The dev server writes `dev-server.log` / `dev-server.err.log` into `DEV_DIR` — ensure those are gitignored: if `<DEV_DIR>/dev-server*.log` (or a broader `dev-server*.log`) isn't already covered by `.gitignore`, add it. After writing the config, go to **step 3**.

**Local-install targets (Tauri / IntelliJ / .NET) — items 2–4:**

2. If **Deploy env** is MISSING, ask the user for `INSTALL_DIR` with a stack-appropriate default and create `config/deploy.env` with `INSTALL_DIR=<their answer>`:
   - **Tauri / .NET** default: `C:/Programs/<project-folder-name>` on Windows, `/Applications/<project-folder-name>` on macOS.
   - **IntelliJ plugin** default: use the **IntelliJ plugins-dir guess** Context value verbatim (it already emits the cross-platform `%APP_CONFIG%/JetBrains/<dir>/plugins` form). If empty (JetBrains dir not found), fall back to `%APP_CONFIG%/JetBrains/IntelliJIdea<newest>/plugins` and ask the user to verify. `%APP_CONFIG%` resolves to `~/AppData/Roaming` on Windows and `~/Library/Application Support` on macOS at deploy time; the legacy `%APPDATA%` placeholder is also accepted as an alias.

   Then apply the stack-specific follow-up questions:
   - **Tauri** — also ask where to deploy the `config/local.json` override at runtime (default: `%APP_CONFIG%/<Tauri identifier>/config.json` — substitute the identifier read from `src-tauri/tauri.conf.json`; use forward slashes) and append `CONFIG_DEST=<their answer>` to `config/deploy.env`. This is the path the app actually reads (`app_data_dir()`), not the install dir.

     **Secrets via Doppler (optional).** If `config/local.json` carries secrets (API tokens, bot credentials, sync tokens), don't keep a plaintext copy on disk — render it from a Doppler-managed template at deploy time. The signal that this is wanted: **Secret config template present** is yes, or the user says the runtime config holds secrets. When so:
     - The committed source is `config/local.template.json` with `{{tojson .SECRET_NAME}}` placeholders for each secret (and literal values for the secret-free settings); the real values live in a Doppler project/config.
     - Ask for the Doppler project and config names (skip if **Deploy env has DOPPLER_PROJECT** ≥ 1 — already set) and append `DOPPLER_PROJECT=<name>` and `DOPPLER_CONFIG=<name>` to `config/deploy.env` (these are not secrets).
     - Ensure the rendered output `config/local.json` is gitignored (it's the transient secret-bearing file). The step-3 wrapper renders the template into it before each deploy and wipes it on exit, so plaintext secrets never sit at rest.

     Skip all of this when the project has no secrets — the trivial wrapper in step 3 is used instead.
   - **IntelliJ plugin** — also ask (optional, skippable) for `IDE_PROCESS` (default = **IntelliJ IDE process guess** Context value) and `IDE_EXE` (default = **IntelliJ IDE exe guess** Context value; if empty — e.g. Toolbox-managed IDE, or running on macOS where the script doesn't auto-detect — offer to skip). On macOS, optionally ask for `IDE_BUNDLE_ID` (e.g. `com.jetbrains.intellij.ce`) — when set, the deploy uses `osascript … to quit` instead of `pkill`. Append `IDE_PROCESS=<value>` / `IDE_EXE=<value>` / `IDE_BUNDLE_ID=<value>` only for keys the user confirms. Skipping is fine — the deploy still works, it just won't stop/restart the IDE.
3. If **Deploy env** is present, the project is **Tauri**, and **Deploy env has CONFIG_DEST** is 0, ask the user for `CONFIG_DEST` with the same default and append it to `config/deploy.env`
4. If **Deploy env** is present, the project is an **IntelliJ plugin**, and **Deploy env has IDE_PROCESS** / **IDE_EXE** are 0, ask the user whether to add them (using the same Context-derived guesses as defaults) and append any values they supply.

## 3. Set up quick deploy shortcut

First decide whether the wrapper needs the Doppler secret-rendering block: it does when `TARGET=deploy-tauri.sh` **and** secrets are managed via Doppler (**Secret config template present** is yes, or **Deploy env has DOPPLER_PROJECT** ≥ 1). Call this **USE_DOPPLER**.

1. Write `scripts/deploy.sh` if **Wrapper script exists** is no, **or** **Wrapper target** does not equal `TARGET` from step 1, **or** USE_DOPPLER is true while **Wrapper renders secrets via Doppler** is no (a Doppler-managed project whose wrapper predates this — regenerate it).

   - **USE_DOPPLER is false** — the trivial pass-through wrapper:
     ```bash
     #!/bin/bash
     bash ~/.claude/skills/deploy/scripts/<TARGET> "$@"
     ```
     (substitute `<TARGET>` with the filename chosen in step 1 — e.g. `deploy-tauri.sh` or `deploy.sh`)
   - **USE_DOPPLER is true** — render the secret template before deploying and wipe it after:
     ```bash
     #!/bin/bash
     # Per-machine deploy wrapper (gitignored). When the Doppler secret template is
     # present, renders secrets into the rendered config, runs the shared Tauri
     # deploy, then removes the rendered file so no plaintext secrets sit in the
     # working tree. Doppler coordinates live in config/deploy.env.
     set -e

     REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
     cd "$REPO_DIR"

     TEMPLATE="config/local.template.json"
     RENDERED="config/local.json"

     if [ -f "$TEMPLATE" ]; then
         DOPPLER_PROJECT=$(grep '^DOPPLER_PROJECT=' config/deploy.env | cut -d= -f2-)
         DOPPLER_CONFIG=$(grep '^DOPPLER_CONFIG=' config/deploy.env | cut -d= -f2-)
         # Wipe the rendered (secret-bearing) config on exit — success, failure, or interrupt.
         trap 'rm -f "$RENDERED"' EXIT
         doppler secrets substitute "$TEMPLATE" \
             --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" > "$RENDERED"
     fi

     bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh "$@"
     ```
     The render is gated on the template existing, so the wrapper still works on a checkout that hasn't set up the template yet. The underlying `deploy-tauri.sh` then copies the rendered `config/local.json` to `CONFIG_DEST`.
2. Keep the wrapper out of git via the **global** excludes file — never the project's `.gitignore`. The wrapper is a per-machine artifact only this skill generates, so it must not land in a repo other contributors share. Ensure the global excludes file contains the line `scripts/deploy.sh` (the mid-string slash anchors it to each repo's root, so it ignores only the wrapper — never a committed `scripts/` source dir):
   ```bash
   gi="$(git config --global core.excludesfile)"; gi="${gi/#\~/$HOME}"; gi="${gi:-$HOME/.gitignore}"
   grep -qxF 'scripts/deploy.sh' "$gi" 2>/dev/null || {
     grep -qF 'per-machine wrappers written by Claude Code' "$gi" 2>/dev/null \
       || printf '\n# per-machine wrappers written by Claude Code deploy/build skills — never committed\n' >> "$gi"
     printf 'scripts/deploy.sh\n' >> "$gi"
   }
   ```
   This covers every repo at once — do not add the wrapper to a project's `.gitignore`. (Project-specific artifacts like the dev-server logs in §2a still go in the project `.gitignore`.)

## 4. Deploy

If step 2 or 3 made changes, tell the user:
> The `deploy` shortcut has been configured. **Restart Claude Code** for `! deploy` to work — the shell reads its rc file only at startup, so new functions aren't available until the next session.
>
> For now, running the deploy directly:

Run the deploy now (bypassing the shell function, which needs a restart to load):
- If **USE_DOPPLER** is true, run the wrapper so the Doppler render runs before the build:
  ```
  bash scripts/deploy.sh
  ```
- Otherwise run the chosen underlying script directly, using `TARGET` from step 1:
  ```
  bash ~/.claude/skills/deploy/scripts/<TARGET>
  ```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! deploy` will work.

**A deploy overwrites the installed config — warn before running one.** When `config/local.json` exists, the deploy copies it over the installed `config.json`, so anything the *app itself* wrote there at runtime — an API key typed into an in-app settings dialog, an OAuth token — is destroyed, silently, if `local.json` carries an empty placeholder for that field. Nothing in the output says a value was lost. Before deploying an app that persists its own settings to the installed config, check `local.json` for empty credential fields and tell the user; the repo's `local.json` is the source of truth, so that is where their keys belong.
