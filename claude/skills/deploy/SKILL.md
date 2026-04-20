---
name: deploy
description: Configure deployment script and run it, verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(bash ~/.claude/skills/deploy/scripts/deploy-tauri.sh), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Read(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Deploy function in bashrc: !`grep -c "deploy()" ~/.bashrc 2>/dev/null || echo 0`
- Wrapper script exists: !`test -f scripts/deploy.sh && echo yes || echo no`
- Wrapper target: !`grep -oE 'deploy(-[a-z]+)?\.sh' scripts/deploy.sh 2>/dev/null | tail -1 || echo none`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`
- Tauri project: !`test -f src-tauri/tauri.conf.json && echo yes || echo no`
- .NET project: !`ls src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`

## 1. Detect project type

Pick the matching underlying deploy script based on the **Context** flags:

- **Tauri project** is yes → `TARGET=deploy-tauri.sh`
- else **.NET project** is yes → `TARGET=deploy.sh`
- else → **STOP**. Tell the user:
  > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`) and .NET (`src/*.csproj`) projects. Neither was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.

  Do not create `config/deploy.env` or the wrapper. Exit.

If both are yes (mixed repo), ask the user which one to deploy — do not guess.

## 2. Check prerequisites

1. If **Deploy function** is 0, append the function to `~/.bashrc`:
   ```bash
   deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
   ```
2. If **Deploy env** is MISSING, ask the user where to install (default: `C:/Programs/<project-folder-name>`) and create `config/deploy.env` with `INSTALL_DIR=<their answer>`

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
