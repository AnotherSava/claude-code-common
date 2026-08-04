---
name: cleanup
description: Configure an uninstall script and run it to remove the app, its data, and its caches from the system — the "before a clean install" counterpart to deploy
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/cleanup/scripts/cleanup-tauri.sh), Bash(cleanup), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(scripts/cleanup.sh), Read(scripts/cleanup.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Edit(~/.zshrc), Read(~/.zshrc)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

The `cleanup` skill is the destructive counterpart to `deploy`: it stops the running app, removes the installed bundle from `INSTALL_DIR`, and wipes the app's user-data + cache directories. It reuses `config/deploy.env` (the same file deploy writes) so the user never has to enter the install location twice.

If `config/deploy.env` contains a `BACKUP_FILES=` line (comma- or space-separated list of paths *inside* the app-data dir), those files are copied to `<repo>/.cleanup-backups/<timestamp>/` **before** the data wipe — use it for per-project files the user would lose work over (e.g. local prompt history, scratch DBs). The `.cleanup-backups/` directory should be in `.gitignore`.

## Context
- Cleanup function in shell rc: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "cleanup()" || echo 0`
- Shell rc target: !`case "$(uname -s)" in Darwin) echo "~/.zshrc" ;; MINGW*|MSYS*|CYGWIN*) echo "~/.bashrc" ;; *) [ -n "$ZSH_VERSION" ] || [ "${SHELL##*/}" = "zsh" ] && echo "~/.zshrc" || echo "~/.bashrc" ;; esac`
- Wrapper script exists: !`test -f scripts/cleanup.sh && echo yes || echo no`
- Wrapper target: !`grep -oE 'cleanup(-[a-z]+)?\.sh' scripts/cleanup.sh 2>/dev/null | tail -1 || echo none`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`
- Deploy env has BACKUP_FILES: !`grep -c '^BACKUP_FILES=' config/deploy.env 2>/dev/null || echo 0`
- Cleanup backups in gitignore: !`grep -cx '.cleanup-backups/' .gitignore 2>/dev/null || echo 0`
- Tauri project: !`test -f src-tauri/tauri.conf.json && echo yes || echo no`
- Tauri identifier: !`sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' src-tauri/tauri.conf.json 2>/dev/null | head -1 || echo none`

## 1. Detect project type

Pick the matching underlying cleanup script based on the **Context** flags:

- **Tauri project** is yes → `TARGET=cleanup-tauri.sh`
- else → **STOP**. Tell the user:
  > The `cleanup` skill currently recognizes Tauri (`src-tauri/tauri.conf.json`) projects. None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/cleanup/scripts/` (mirroring the deploy skill's stack-specific scripts) and extend this skill.

  Do not create the wrapper. Exit.

## 2. Check prerequisites

1. If **Cleanup function in shell rc** is 0, append the function to the file in **Shell rc target** (i.e. `~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux-bash):
   ```bash
   cleanup() { if [ -f scripts/cleanup.sh ]; then bash scripts/cleanup.sh "$@"; else echo "No scripts/cleanup.sh in current directory"; fi; }
   ```
2. If **Deploy env** is MISSING, do **not** create one here — the cleanup script falls back to a stack-appropriate default `INSTALL_DIR` and warns. The user should run the `deploy` skill first if they want the path captured.
3. If **Cleanup backups in gitignore** is 0, append `.cleanup-backups/` to `.gitignore` so timestamped backup directories don't end up committed. Do this whether or not the project has `BACKUP_FILES` configured today — adding it later won't surprise the user with new tracked files.

## 3. Set up quick cleanup shortcut

1. If **Wrapper script exists** is no, **or** **Wrapper target** does not equal `TARGET` from step 1, write `scripts/cleanup.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/cleanup/scripts/<TARGET> "$@"
   ```
   (substitute `<TARGET>` with the filename chosen in step 1 — e.g. `cleanup-tauri.sh`)
2. If **Scripts in gitignore** is 0, append to `.gitignore`:
   ```
   # Local convenience scripts (not committed)
   scripts/
   ```

## 4. Confirm scope, then clean

Before running the script, confirm with the user **which targets** to remove. Cleanup is destructive (the app's saved config, custom names, dialog history, etc. all live in the app-data dir), so always ask — even when the user just typed `/cleanup` with no qualifier. Use `AskUserQuestion` with a `multiSelect: true` question listing:

- **Installed app bundle** — the `.app` / `.exe` at `INSTALL_DIR`
- **App data** — `~/Library/Application Support/<identifier>` on macOS, `%APPDATA%/<identifier>` on Windows
- **Caches** — `~/Library/Caches/<identifier>` on macOS, `%LOCALAPPDATA%/<identifier>` on Windows

Default the question to all three selected (recommended for a true clean install). Translate the user's selection into the script's `--keep-*` flags — the script removes all three by default, so pass a `--keep-X` flag for every box the user **unchecked**.

If step 2 or 3 made changes, also tell the user:
> The `cleanup` shortcut has been configured. **Restart Claude Code** for `! cleanup` to work — the shell reads its rc file only at startup, so new functions aren't available until the next session.
>
> For now, running cleanup directly:

Then run the underlying script with the derived flags, using `TARGET` from step 1:
```
bash ~/.claude/skills/cleanup/scripts/<TARGET> [--keep-bundle] [--keep-data] [--keep-cache]
```

Report the output to the user. The script always prints which paths it actually removed (vs. were already absent), so the report should make clear what state remained.

On success, suggest the next step:
> Cleanup complete. Run `deploy` (or `! deploy`) to perform the clean install.
