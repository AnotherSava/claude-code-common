---
name: deploy
description: Configure deployment script and run it, verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), Bash(deploy), Bash(echo *), Bash(source ~/.bashrc), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Write(scripts/deploy.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc)
---

## Context
- Deploy function in bashrc: !`grep -c "deploy()" ~/.bashrc 2>/dev/null || echo 0`
- Wrapper script exists: !`test -f scripts/deploy.sh && echo yes || echo no`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`

## 1. Check prerequisites

1. If **Deploy function** is 0, append the function to `~/.bashrc`:
   ```bash
   deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
   ```
   Then source it to apply immediately:
   ```bash
   source ~/.bashrc
   ```
2. If **Deploy env** is MISSING, ask the user where to install (default: `C:/Programs/<project-folder-name>`) and create `config/deploy.env` with `INSTALL_DIR=<their answer>`

## 2. Set up quick deploy shortcut

1. If **Wrapper script exists** is no, create `scripts/deploy.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/deploy/scripts/deploy.sh "$@"
   ```
2. If **Scripts in gitignore** is 0, append to `.gitignore`:
   ```
   # Local convenience scripts (not committed)
   scripts/
   ```

## 3. Deploy

Run the deploy function to verify the full shortcut chain works:
```
deploy
```

This exercises the function → `scripts/deploy.sh` → global deploy script pipeline. The script reads `config/deploy.env` for `INSTALL_DIR`, auto-detects the project from `src/*.csproj`, and handles: stop app → build → clean → copy → launch → verify.

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, tell the user they can use `! deploy` for faster deployment next time (bypasses the LLM).
