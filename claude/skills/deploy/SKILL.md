---
name: deploy
description: Configure deployment script and run it, verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-intellij-plugin.sh), Bash(bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh:*), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Read(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Deploy function in bashrc: !`grep -c "deploy()" ~/.bashrc 2>/dev/null || echo 0`
- Wrapper script exists: !`test -f scripts/deploy.sh && echo yes || echo no`
- Wrapper target: !`grep -oE 'deploy(-[a-z]+)?\.sh' scripts/deploy.sh 2>/dev/null | tail -1 || echo none`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
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

- **Tauri project** is yes → `TARGET=deploy-tauri.sh`
- else **IntelliJ plugin project** is yes → `TARGET=deploy-intellij-plugin.sh`
- else **.NET project** is yes → `TARGET=deploy.sh`
- else → **STOP**. Tell the user:
  > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`), IntelliJ plugins (`build.gradle[.kts]` using `org.jetbrains.intellij[.platform]`), and .NET (`src/*.csproj`) projects. None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.

  Do not create `config/deploy.env` or the wrapper. Exit.

If more than one flag is yes (mixed repo), ask the user which one to deploy — do not guess.

## 2. Check prerequisites

1. If **Deploy function** is 0, append the function to `~/.bashrc`:
   ```bash
   deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
   ```
2. If **Deploy env** is MISSING, ask the user for `INSTALL_DIR` with a stack-appropriate default and create `config/deploy.env` with `INSTALL_DIR=<their answer>`:
   - **Tauri / .NET** default: `C:/Programs/<project-folder-name>`
   - **IntelliJ plugin** default: use the **IntelliJ plugins-dir guess** Context value verbatim. If empty (JetBrains dir not found), fall back to `%APPDATA%/JetBrains/IntelliJIdea<newest>/plugins` and ask the user to verify.

   Then apply the stack-specific follow-up questions:
   - **Tauri** — also ask where to deploy the `config/local.json` override at runtime (default: `%APPDATA%/<Tauri identifier>/config.json` — substitute the identifier read from `src-tauri/tauri.conf.json`; use forward slashes) and append `CONFIG_DEST=<their answer>` to `config/deploy.env`. This is the path the app actually reads (`app_data_dir()`), not the install dir.
   - **IntelliJ plugin** — also ask (optional, skippable) for `IDE_PROCESS` (default = **IntelliJ IDE process guess** Context value) and `IDE_EXE` (default = **IntelliJ IDE exe guess** Context value; if empty — e.g. Toolbox-managed IDE — offer to skip). Append `IDE_PROCESS=<value>` / `IDE_EXE=<value>` only for keys the user confirms. Skipping is fine — the deploy still works, it just won't stop/restart the IDE.
3. If **Deploy env** is present, the project is **Tauri**, and **Deploy env has CONFIG_DEST** is 0, ask the user for `CONFIG_DEST` with the same default and append it to `config/deploy.env`
4. If **Deploy env** is present, the project is an **IntelliJ plugin**, and **Deploy env has IDE_PROCESS** / **IDE_EXE** are 0, ask the user whether to add them (using the same Context-derived guesses as defaults) and append any values they supply.

## 3. Set up quick deploy shortcut

1. If **Wrapper script exists** is no, **or** **Wrapper target** does not equal `TARGET` from step 1, write `scripts/deploy.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/deploy/scripts/<TARGET> "$@"
   ```
   (substitute `<TARGET>` with the filename chosen in step 1 — e.g. `deploy-tauri.sh` or `deploy.sh`)
2. If **Scripts in gitignore** is 0, append to `.gitignore`:
   ```
   # Local convenience scripts (not committed)
   scripts/
   ```

## 4. Deploy

If step 2 or 3 made changes, tell the user:
> The `deploy` shortcut has been configured. **Restart Claude Code** for `! deploy` to work — the shell reads `~/.bashrc` only at startup, so new functions aren't available until the next session.
>
> For now, running the deploy directly:

Run the chosen underlying script directly (bypassing the shell function), using `TARGET` from step 1:
```
bash ~/.claude/skills/deploy/scripts/<TARGET>
```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! deploy` will work.
