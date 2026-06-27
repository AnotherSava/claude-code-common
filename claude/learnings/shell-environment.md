# Shell Environment

Shell configuration across the user's environments. Use this to verify correct setup when running Claude Code in a new shell (e.g. WSL) or diagnosing missing functions/aliases.

## Shells and config files

| Shell | Config file |
|---|---|
| Git Bash (Windows) | `~/.bashrc` |
| WSL Ubuntu | `/home/sava/.bashrc` |
| macOS zsh | `~/.zshrc` (interactive). Put `export` lines that need to apply to non-interactive shells (cron, hooks) in `~/.zshenv` instead. |
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
- **macOS:** drop the same function in `~/.zshrc` (zsh) or `~/.bash_profile` (bash). The OSC 0 escape sets the tab title in Terminal.app and iTerm2 too. The `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` line is harmless on macOS — the per-tick overwrite that justifies it on Windows Terminal doesn't happen here, but the export is a no-op when the override doesn't trigger.

### `deploy` / `build` — project shortcuts

```bash
deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
build()  { if [ -f scripts/build.sh ]; then bash scripts/build.sh "$@"; else echo "No scripts/build.sh in current directory"; fi; }
```

Use `! deploy` or `! build` inside Claude Code, or run directly in any terminal. Each project has a `scripts/deploy.sh` and/or `scripts/build.sh` (gitignored) that delegates to the global script in the corresponding skill directory.

### `memo` — fast backlog access

```bash
memo() {
  local py="$HOME/.claude/skills/memo/memos.py" w c
  if [ $# -gt 0 ]; then python "$py" add "$@"; return; fi
  if [ -n "$MEMO_WIDTH" ]; then w=$MEMO_WIDTH
  elif [ -n "$CLAUDECODE" ]; then w=148   # captured CC `!` shell can't detect width — pin to (window − indent − gutter)
  else c=$(tput cols 2>/dev/null || echo 100); w=$(( c > 40 ? c - 2 : 98 )); fi
  python "$py" list --width "$w"
}
```

`! memo` (or `memo` in any terminal) prints the open backlog at full width in ~0.1 s; `memo <text>` appends that text as a new memo (no quotes needed). This is the **model-free** path — the `/memo` skill is slow because it drives the model through multi-step tool calls, wasted effort for a plain list/append. Reach for the skill only when you want model help: cleaning up an idea on capture, or reviewing with offers to act on items.

**Width (and a Claude Code gotcha).** A real terminal auto-detects (bash `tput cols`, PowerShell `$Host…WindowSize.Width`). But Claude Code captures `!`-command stdout with no tty, so `tput cols` returns the `xterm` default (80) — the real window is unreachable. **Two facts make this work:** (1) Claude Code syncs `.bashrc` *functions* into the `!` shell but **not** its top-level `export`s — so a `MEMO_WIDTH` export in `.bashrc` never reaches `! memo`; the pinned value must live *inside the function*. (2) `CLAUDECODE=1` *is* in CC's environment (it's not from `.bashrc`), so it's the reliable "captured context" flag. Hence: gate the pin on `CLAUDECODE` and hard-code this machine's CC width in the function body; a real terminal (no `CLAUDECODE`) falls through to `tput`. **Set the pin to `window − ~4 − 2`, not the raw window**: CC renders `!`-command output under a `└` tree prefix that indents it ~4 columns, so wrapping at the full width overflows and the terminal re-wraps the overflow (e.g. 156-col window → pin ≈ 148). Adjust the number if you resize.

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

## PowerShell `memo` wrapper

```powershell
function memo {
    $py = "$HOME\.claude\skills\memo\memos.py"
    if ($args.Count -gt 0) { python $py add @args; return }
    $w = if ($env:MEMO_WIDTH) { [int]$env:MEMO_WIDTH } else { [Math]::Max(40, $Host.UI.RawUI.WindowSize.Width - 2) }
    python $py list --width $w
}
```

Same as the bash `memo` — fast, model-free backlog access (`memo` to list, `memo <text>` to add).

## Verification checklist

When setting up a new shell (e.g. WSL), verify:

1. **`claude` function exists** — `type claude` should show the function, not the binary path
2. **`deploy` function exists** — `type deploy`
3. **`build` function exists** — `type build`
4. **`memo` function exists** — `type memo`
5. **`notify` function exists** — `type notify`
6. **Python + deps available** — `python3 -c "import requests, dotenv"` (needed by `notify` and Claude hooks)
7. **macOS only:** confirm `python3` resolves at all — Apple removed the bundled `python` in recent macOS releases. Install via `brew install python` (or use the Xcode Command Line Tools shim) before running step 6.
8. **Symlinks intact** — `ls -la ~/.claude` should point to the claude-code-common repo's `claude/` directory
9. **Git hooks linked** — `git config --global core.hooksPath` should return `~/.git-hooks`
