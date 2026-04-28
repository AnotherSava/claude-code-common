# Shell Environment

Shell configuration across the user's environments. Use this to verify correct setup when running Claude Code in a new shell (e.g. WSL) or diagnosing missing functions/aliases.

## Shells and config files

| Shell | Config file |
|---|---|
| Git Bash (Windows) | `~/.bashrc` |
| WSL Ubuntu | `/home/sava/.bashrc` |
| PowerShell 7 | `Documents/PowerShell/Microsoft.PowerShell_profile.ps1` |
| PowerShell 5 | `Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1` |

## Bash functions (`~/.bashrc`)

All bash shells (Git Bash, WSL) should have these functions:

### `claude` — wrapper with auto-continue

```bash
claude() {
  printf '\033]0;CC %s\a' "${PWD##*/}"
  export CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
  if [[ "$1" == "--new" ]]; then
    shift
    command claude "$@"
  else
    command claude --continue "$@"
    if [[ $? -ne 0 ]]; then
      command claude "$@"
    fi
  fi
  [[ $? -eq 0 ]] && clear
}
```

- `claude` → resumes last conversation (`--continue`). Falls back to fresh session if none exists.
- `claude --new` → fresh conversation.
- Sets the Windows Terminal tab title to `CC <project-folder>` via OSC 0 escape. `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` is required because Claude Code otherwise overwrites the title with `⠐ Claude Code` on every tick (see `windows-terminal-title.md`).
- Screen clears on success; preserved on error so the message is readable.

### `deploy` / `build` — project shortcuts

```bash
deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
build()  { if [ -f scripts/build.sh ]; then bash scripts/build.sh "$@"; else echo "No scripts/build.sh in current directory"; fi; }
```

Use `! deploy` or `! build` inside Claude Code, or run directly in any terminal. Each project has a `scripts/deploy.sh` and/or `scripts/build.sh` (gitignored) that delegates to the global script in the corresponding skill directory.

## PowerShell `claude` wrapper

```powershell
function claude {
    $Host.UI.RawUI.WindowTitle = "CC $(Split-Path -Leaf (Get-Location))"
    $env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE = "1"
    if ($args[0] -eq '--new') {
        & claude.cmd @($args[1..$args.Length])
    } else {
        & claude.cmd --continue @args
        if ($LASTEXITCODE -ne 0) { & claude.cmd @args }
    }
    if ($LASTEXITCODE -eq 0) { Clear-Host }
}
```

Same behavior as the bash version. PowerShell re-asserts its own title on each prompt render after Claude exits.

## Verification checklist

When setting up a new shell (e.g. WSL), verify:

1. **`claude` function exists** — `type claude` should show the function, not the binary path
2. **`deploy` function exists** — `type deploy`
3. **`build` function exists** — `type build`
4. **`notify` function exists** — `type notify`
5. **Python + deps available** — `python3 -c "import requests, dotenv"` (needed by `notify` and Claude hooks)
6. **Symlinks intact** — `ls -la ~/.claude` should point to the claude-code-common repo's `claude/` directory
7. **Git hooks linked** — `git config --global core.hooksPath` should return `~/.git-hooks`
