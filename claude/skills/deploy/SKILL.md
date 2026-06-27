---
name: deploy
description: Configure deployment script and run it, verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-intellij-plugin.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-cloudflare-pages.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-dev-server.sh), Bash(bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh:*), Bash(bash scripts/deploy.sh), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Read(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Edit(~/.zshrc), Read(~/.zshrc)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Deploy function in shell rc: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "deploy()" || echo 0`
- Shell rc target: !`case "$(uname -s)" in Darwin) echo "~/.zshrc" ;; MINGW*|MSYS*|CYGWIN*) echo "~/.bashrc" ;; *) [ -n "$ZSH_VERSION" ] || [ "${SHELL##*/}" = "zsh" ] && echo "~/.zshrc" || echo "~/.bashrc" ;; esac`
- Wrapper script exists: !`test -f scripts/deploy.sh && echo yes || echo no`
- Wrapper target: !`grep -oE 'deploy(-[a-z]+)?\.sh' scripts/deploy.sh 2>/dev/null | tail -1 || echo none`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
- Scripts dir has tracked files: !`git ls-files scripts/ 2>/dev/null | grep -q . && echo yes || echo no`
- Cloudflare Pages configured: !`grep -c '^DEPLOY_TYPE=cloudflare-pages' config/deploy.env 2>/dev/null || echo 0`
- Wrangler config present: !`(test -f wrangler.toml || test -f wrangler.json || test -f wrangler.jsonc) && echo yes || echo no`
- package.json build script: !`node -e "try{process.stdout.write(require('./package.json').scripts&&require('./package.json').scripts.build?'yes':'no')}catch(e){process.stdout.write('no')}" 2>/dev/null || echo no`
- Static web entry (index.html): !`(ls index.html web/index.html public/index.html src/index.html dist/index.html 2>/dev/null | grep -q .) && echo yes || echo no`
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

- **Cloudflare Pages configured** ≥ 1 (`config/deploy.env` marks `DEPLOY_TYPE=cloudflare-pages`) → `TARGET=deploy-cloudflare-pages.sh`
- else **Dev-server configured** ≥ 1 (`config/deploy.env` marks `DEPLOY_TYPE=dev-server`) → `TARGET=deploy-dev-server.sh`
- else **Tauri project** is yes → `TARGET=deploy-tauri.sh`
- else **IntelliJ plugin project** is yes → `TARGET=deploy-intellij-plugin.sh`
- else **.NET project** is yes → `TARGET=deploy.sh`
- else decide from two signals — **Cloud target** = (**Wrangler config present** is yes **or** **Static web entry (index.html)** is yes), and **Dev server** = (**Dev-server dir** is non-empty, i.e. a `package.json` with a `dev` script was found):
  - **both** present (e.g. a Vite SPA you both run locally and ship to Pages) → ask the user what `deploy` should mean here:
    > This project can be deployed two ways. What should `deploy` do? **(a)** Restart the local dev server (run it on this machine), or **(b)** Ship a build to Cloudflare Pages?

    (a) → `TARGET=deploy-dev-server.sh` (§2b); (b) → `TARGET=deploy-cloudflare-pages.sh` (§2a).
  - only **Cloud target** → ask the user:
    > This looks like a static web project. Deploy it to **Cloudflare Pages** (build + `wrangler` direct upload)?

    If yes → `TARGET=deploy-cloudflare-pages.sh` (§2a). If no → **STOP** with the message below.
  - only **Dev server** (a web app you develop and run locally — Next.js, Remix, SvelteKit, a plain Node server — with no install/cloud target) → `TARGET=deploy-dev-server.sh` (§2b). Here `deploy` means "restart the local dev server" — the run-it-for-me counterpart to the install targets, not a production ship.
  - **neither** → **STOP**. Tell the user:
    > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`), IntelliJ plugins (`build.gradle[.kts]` using `org.jetbrains.intellij[.platform]`), .NET (`src/*.csproj`), local dev servers (a `package.json` with a `dev` script), and static sites deployed to Cloudflare Pages. None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.

    Do not create `config/deploy.env` or the wrapper. Exit.

The local-install types (Tauri / IntelliJ / .NET) and the local dev server are mutually exclusive with Cloudflare Pages (cloud). If more than one local target's flag is yes (mixed repo), ask the user which one to deploy — do not guess.

## 2. Check prerequisites

1. If **Deploy function in shell rc** is 0, append the function to the file in **Shell rc target** (i.e. `~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux-bash):
   ```bash
   deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
   ```

**If `TARGET` is `deploy-cloudflare-pages.sh`, configure via §2a and skip items 2–4. If `TARGET` is `deploy-dev-server.sh`, configure via §2b and skip items 2–4. (Items 2–4 are for the local-install targets.)**

### 2a. Cloudflare Pages configuration

Write `config/deploy.env` with these keys (ask only for keys not already present; use the Context-derived defaults):

- `DEPLOY_TYPE=cloudflare-pages` — always write this; it's the marker that routes future runs straight to this target.
- `CF_PAGES_PROJECT=` — the Pages project name. Default = **Repo folder name** lowercased with any character outside `[a-z0-9-]` replaced by `-`. The deploy script auto-creates the project on first run if it doesn't exist.
- `OUTPUT_DIR=` — directory uploaded to Pages (relative to repo root). Default `dist` (common alternatives: `build`, `out`, `public`).
- `BUILD_CMD=` — command that produces `OUTPUT_DIR`. Derive the default:
  - if `scripts/build_site.mjs` exists → `node --env-file=.env scripts/build_site.mjs`
  - else if **package.json build script** is yes → `npm run build`
  - else → leave empty (the script uploads `OUTPUT_DIR` as-is)
- `BRANCH=` — deploy branch. Default = **Production branch** Context value; deploys equal the production branch are production deploys.

Then handle auth and secrets:

1. The deploy reads `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from the project's `.env` at deploy time (or falls back to a prior `wrangler login`). If `.env` has neither and there's no wrangler session, tell the user to add them to `.env` or run `! npx wrangler login`. The token needs **Account → Cloudflare Pages → Edit** (add **Zone → DNS → Edit** only if managing the custom domain via API too).
2. Ensure `.env` is gitignored (it holds the Cloudflare token) — if it isn't in `.gitignore`, add it.

`config/deploy.env` holds no secrets (only project/build settings), so it is safe to commit. After writing it, go to **step 3**.

### 2b. Dev-server configuration

For a local dev server, `deploy` stops whatever holds the port and relaunches the dev command detached (so it outlives the Claude session), then waits for the port to come up. Write `config/deploy.env` with these keys (ask only for keys not already present; use the Context-derived defaults — confirm them with the user rather than asking blind):

- `DEPLOY_TYPE=dev-server` — always write this; it's the marker that routes future runs straight to this target.
- `DEV_DIR=` — subdir holding the `package.json` with the `dev` script, relative to repo root. Default = **Dev-server dir** Context value (`.` for a root app, e.g. `web` for a monorepo subdir).
- `DEV_PORT=` — port the server listens on (used to stop the old instance and health-check the new one). Default = **Dev-server port guess** Context value if non-empty, else `3000` (note: Vite defaults to `5173`). Confirm with the user — the guess only catches ports written explicitly in the dev script.
- `DEV_CMD=` — command that starts the server. Default = **Dev-server start command guess** Context value (picks `pnpm`/`yarn`/`bun`/`npm` from the lockfile). Keep it as the package-manager script (e.g. `npm run dev`) even when that script itself wraps another tool (Doppler, env loaders) — the wrapping lives in `package.json`, not here.

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
2. Keep the wrapper out of git, without clobbering a tracked `scripts/` dir:
   - If **Scripts dir has tracked files** is yes (the project commits other scripts — common for static/Cloudflare Pages repos), append only the wrapper to `.gitignore` (if not already present):
     ```
     # Local convenience wrapper (not committed)
     scripts/deploy.sh
     ```
   - else if **Scripts in gitignore** is 0, append the whole dir:
     ```
     # Local convenience scripts (not committed)
     scripts/
     ```

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
