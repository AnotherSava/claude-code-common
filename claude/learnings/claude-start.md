# Claude Code Shell Wrapper

The user has a shell wrapper for `claude` that defaults to `--continue` (resume last conversation). A fresh session requires `claude --new`. Both variants clear the screen on exit.

Configured in 4 shells:

### Bash
- Git Bash: `~/.bashrc`
- WSL Ubuntu: `/home/sava/.bashrc`

```bash
claude() {
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

### PowerShell
- PS7: `Documents/PowerShell/Microsoft.PowerShell_profile.ps1`
- PS5: `Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1`

```powershell
function claude {
    if ($args[0] -eq '--new') {
        & claude.cmd @($args[1..$args.Length])
    } else {
        & claude.cmd --continue @args
        if ($LASTEXITCODE -ne 0) { & claude.cmd @args }
    }
    if ($LASTEXITCODE -eq 0) { Clear-Host }
}
```

## Behavior

- `claude` → `claude --continue` (resume previous conversation, since most launches are continuations). If `--continue` fails (e.g., "No conversation found"), retries without it to start a fresh session.
- `claude --new` → `claude` without `--continue` (fresh conversation)
- Screen clears after exit only on success (`$?`/`$LASTEXITCODE` == 0) — Claude outputs below the current cursor position, and the shell doesn't clear those lines on exit, leaving stale output visible. On error, the screen is preserved so the error is readable.

## Implication

When the user says they "restarted" or "relaunched" Claude Code, they likely resumed the same conversation (unless they explicitly used `--new`). Context from the previous session carries over.
