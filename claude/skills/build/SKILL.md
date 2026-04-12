---
name: build
description: Configure build script and run it
allowed-tools: Bash(bash ~/.claude/skills/build/scripts/build.sh), Bash(build), Bash(echo *), AskUserQuestion, Write(scripts/build.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Build function in bashrc: !`grep -c "build()" ~/.bashrc 2>/dev/null || echo 0`
- Wrapper script exists: !`test -f scripts/build.sh && echo yes || echo no`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`

## 1. Check prerequisites

1. If **Build function** is 0, append the function to `~/.bashrc`:
   ```bash
   build() { if [ -f scripts/build.sh ]; then bash scripts/build.sh "$@"; else echo "No scripts/build.sh in current directory"; fi; }
   ```

## 2. Set up quick build shortcut

1. If **Wrapper script exists** is no, create `scripts/build.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/build/scripts/build.sh "$@"
   ```
2. If **Scripts in gitignore** is 0, append to `.gitignore`:
   ```
   # Local convenience scripts (not committed)
   scripts/
   ```

## 3. Build

If step 1 or 2 made changes, tell the user:
> The `build` shortcut has been configured. **Restart Claude Code** for `! build` to work — the shell reads `~/.bashrc` only at startup, so new functions aren't available until the next session.
>
> For now, running the build directly:

Run the build script directly (bypassing the shell function):
```
bash ~/.claude/skills/build/scripts/build.sh
```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! build` will work.
