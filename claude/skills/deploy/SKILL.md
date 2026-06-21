---
name: deploy
description: Configure deployment script and run it, verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-intellij-plugin.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-cloudflare-pages.sh), Bash(bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh:*), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Read(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Edit(~/.zshrc), Read(~/.zshrc)
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
- Repo folder name: !`basename "$(pwd)"`
- Production branch: !`git symbolic-ref --short HEAD 2>/dev/null || echo main`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`
- Deploy env has CONFIG_DEST: !`grep -c '^CONFIG_DEST=' config/deploy.env 2>/dev/null || echo 0`
- Tauri project: !`test -f src-tauri/tauri.conf.json && echo yes || echo no`
- Tauri identifier: !`sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' src-tauri/tauri.conf.json 2>/dev/null | head -1 || echo none`
- .NET project: !`ls src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ plugin project: !`(test -f build.gradle.kts || test -f build.gradle) && grep -lE 'org\.jetbrains\.intellij(\.platform)?' build.gradle.kts build.gradle 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ target type: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh type 2>/dev/null || echo unknown`
- IntelliJ plugins-dir guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh plugins-dir 2>/dev/null || echo`
- IntelliJ IDE exe guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-exe 2>/dev/null || echo`
- IntelliJ IDE process guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-process 2>/dev/null || echo`
- Deploy env has IDE_PROCESS: !`grep -c '^IDE_PROCESS=' config/deploy.env 2>/dev/null || echo 0`
- Deploy env has IDE_EXE: !`grep -c '^IDE_EXE=' config/deploy.env 2>/dev/null || echo 0`

## 1. Detect project type

Pick the matching underlying deploy script based on the **Context** flags:

- **Cloudflare Pages configured** ≥ 1 (already set up — `config/deploy.env` marks `DEPLOY_TYPE=cloudflare-pages`) → `TARGET=deploy-cloudflare-pages.sh`
- else **Tauri project** is yes → `TARGET=deploy-tauri.sh`
- else **IntelliJ plugin project** is yes → `TARGET=deploy-intellij-plugin.sh`
- else **.NET project** is yes → `TARGET=deploy.sh`
- else if **Wrangler config present** is yes, **or** **Static web entry (index.html)** is yes (a static / web app with no local-install target) → ask the user:
  > This looks like a static web project. Deploy it to **Cloudflare Pages** (build + `wrangler` direct upload)?

  If yes → `TARGET=deploy-cloudflare-pages.sh` (and write `DEPLOY_TYPE=cloudflare-pages` into `config/deploy.env` in step 2). If no → **STOP** with the message below.
- else → **STOP**. Tell the user:
  > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`), IntelliJ plugins (`build.gradle[.kts]` using `org.jetbrains.intellij[.platform]`), .NET (`src/*.csproj`), and static sites deployed to Cloudflare Pages. None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.

  Do not create `config/deploy.env` or the wrapper. Exit.

The local-install types (Tauri / IntelliJ / .NET) are mutually exclusive with Cloudflare Pages (cloud). If more than one local-install flag is yes (mixed repo), ask the user which one to deploy — do not guess.

## 2. Check prerequisites

1. If **Deploy function in shell rc** is 0, append the function to the file in **Shell rc target** (i.e. `~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux-bash):
   ```bash
   deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
   ```

**If `TARGET` is `deploy-cloudflare-pages.sh`, configure via §2a and skip items 2–4 (those are for local-install targets).**

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

**Local-install targets (Tauri / IntelliJ / .NET) — items 2–4:**

2. If **Deploy env** is MISSING, ask the user for `INSTALL_DIR` with a stack-appropriate default and create `config/deploy.env` with `INSTALL_DIR=<their answer>`:
   - **Tauri / .NET** default: `C:/Programs/<project-folder-name>` on Windows, `/Applications/<project-folder-name>` on macOS.
   - **IntelliJ plugin** default: use the **IntelliJ plugins-dir guess** Context value verbatim (it already emits the cross-platform `%APP_CONFIG%/JetBrains/<dir>/plugins` form). If empty (JetBrains dir not found), fall back to `%APP_CONFIG%/JetBrains/IntelliJIdea<newest>/plugins` and ask the user to verify. `%APP_CONFIG%` resolves to `~/AppData/Roaming` on Windows and `~/Library/Application Support` on macOS at deploy time; the legacy `%APPDATA%` placeholder is also accepted as an alias.

   Then apply the stack-specific follow-up questions:
   - **Tauri** — also ask where to deploy the `config/local.json` override at runtime (default: `%APP_CONFIG%/<Tauri identifier>/config.json` — substitute the identifier read from `src-tauri/tauri.conf.json`; use forward slashes) and append `CONFIG_DEST=<their answer>` to `config/deploy.env`. This is the path the app actually reads (`app_data_dir()`), not the install dir.
   - **IntelliJ plugin** — also ask (optional, skippable) for `IDE_PROCESS` (default = **IntelliJ IDE process guess** Context value) and `IDE_EXE` (default = **IntelliJ IDE exe guess** Context value; if empty — e.g. Toolbox-managed IDE, or running on macOS where the script doesn't auto-detect — offer to skip). On macOS, optionally ask for `IDE_BUNDLE_ID` (e.g. `com.jetbrains.intellij.ce`) — when set, the deploy uses `osascript … to quit` instead of `pkill`. Append `IDE_PROCESS=<value>` / `IDE_EXE=<value>` / `IDE_BUNDLE_ID=<value>` only for keys the user confirms. Skipping is fine — the deploy still works, it just won't stop/restart the IDE.
3. If **Deploy env** is present, the project is **Tauri**, and **Deploy env has CONFIG_DEST** is 0, ask the user for `CONFIG_DEST` with the same default and append it to `config/deploy.env`
4. If **Deploy env** is present, the project is an **IntelliJ plugin**, and **Deploy env has IDE_PROCESS** / **IDE_EXE** are 0, ask the user whether to add them (using the same Context-derived guesses as defaults) and append any values they supply.

## 3. Set up quick deploy shortcut

1. If **Wrapper script exists** is no, **or** **Wrapper target** does not equal `TARGET` from step 1, write `scripts/deploy.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/deploy/scripts/<TARGET> "$@"
   ```
   (substitute `<TARGET>` with the filename chosen in step 1 — e.g. `deploy-tauri.sh` or `deploy.sh`)
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

Run the chosen underlying script directly (bypassing the shell function), using `TARGET` from step 1:
```
bash ~/.claude/skills/deploy/scripts/<TARGET>
```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! deploy` will work.
