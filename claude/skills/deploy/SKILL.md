---
name: deploy
description: Build and deploy a .NET project to its local install directory
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/deploy.sh), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env)
---

Run the deploy script:
```
bash ~/.claude/skills/deploy/scripts/deploy.sh
```

The script reads `config/deploy.env` for `INSTALL_DIR`, auto-detects the project from `src/*.csproj`, and handles: stop app → build → clean → copy → launch → verify.

Report the output to the user. If it fails:
- If `config/deploy.env` is missing, ask the user where to install (default: `C:/Programs/<project-folder-name>`) and create the file
- Otherwise analyze the error and suggest a fix

## Quick deploy shortcut

For faster deploys without LLM overhead, use `! deploy` from the prompt. This runs a local `scripts/deploy.sh` in the project root via a bash alias.

### Setup

1. Create `scripts/deploy.sh` in the project root:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/deploy/scripts/deploy.sh
   ```

2. Add to `~/.bashrc`:
   ```bash
   alias deploy='if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh; else echo "No scripts/deploy.sh in current directory"; fi'
   ```

3. Add `scripts/` to `.gitignore` (local convenience, not committed)
