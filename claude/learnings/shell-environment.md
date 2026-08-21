# Shell Environment

Shell configuration across the user's environments. Use this to verify correct setup when running Claude Code in a new shell (e.g. WSL) or diagnosing missing functions/aliases.

## Shells and config files

| Shell | Config file |
|---|---|
| Git Bash (Windows) | `~/.bashrc` |
| WSL Ubuntu | `~/.bashrc` |
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

### `deploy` / `build` / `publish` / `cb` — project shortcuts

```bash
run_repo_script() { local rel="$1"; shift; local d="$PWD"; while [ "$d" != "/" ] && [ ! -f "$d/$rel" ]; do d="$(dirname "$d")"; done; if [ -f "$d/$rel" ]; then ( cd "$d" && bash "$rel" "$@" ); else echo "No $rel in this directory or any parent"; fi; }
deploy() { run_repo_script scripts/deploy.sh "$@"; }
build()  { run_repo_script scripts/build.sh "$@"; }
# Ship a project live — the counterpart to `deploy`, which only runs/installs it here.
# Kept separate so nothing publishes by accident.
publish() { run_repo_script scripts/publish.sh "$@"; }
# Re-copy the value Claude last put on the clipboard, for when something has overwritten it since.
# The script is regenerated on every copy, so it always holds the most recent one.
cb() { run_repo_script scripts/cb.sh "$@"; }
```

Use `! deploy`, `! build`, `! publish` or `! cb` inside Claude Code, or run directly in any terminal. They all delegate to `run_repo_script`, which walks up from the current directory to the repo's `scripts/<name>.sh` and runs it from the directory that holds it — so they work from any subdirectory (the underlying scripts read `config/deploy.env` and other paths relative to that root). `run_repo_script` is generic: reuse it for any future repo shortcut. Each project carries whichever of `scripts/deploy.sh`, `scripts/build.sh`, `scripts/publish.sh` and `scripts/cb.sh` it actually needs, each a thin wrapper delegating to the global script in the corresponding skill directory — and a project that publishes from CI deliberately has no `publish.sh` at all. All of them are gitignored via the global excludes file, where one narrow rule covers every repo, so nothing leaks into a shared project's committed `.gitignore`.

`cb` is the odd one out: its script is not written once at setup but **regenerated every time Claude puts a
value on the user's clipboard**, so `cb` always hands back the most recent one. It holds the command that
*retrieves* the value (normally a `doppler secrets get`), never the value itself — so no secret sits in
plaintext on disk and a rotation can't leave it serving a dead credential. See the doppler skill.

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
4. **`publish` function exists** — `type publish`
5. **`memo` function exists** — `type memo`
6. **`notify` function exists** — `type notify`
7. **A real `python` on `PATH`** — `python -V`. Hooks and the statusline invoke the bare name, never `python3`, because `python3` is an indirection on both platforms (bash shim on Windows, `xcode-select` dispatcher on macOS). A machine without it runs no hooks, silently.
8. **macOS only:** Apple ships no `python`, and the Command Line Tools `python3` is 3.9 — old enough that `str | None` annotations fail at import. Run `brew install python && ln -s /opt/homebrew/bin/python3 ~/.local/bin/python`, and check `~/.local/bin` is on `PATH`. See the README's [Python interpreter](../../README.md#python-interpreter) section.
9. **Deps for `notify`** — `python -c "import requests, dotenv"`. The Claude hooks themselves are stdlib-only, so this gates `notify`, not them.
10. **Symlinks intact** — `ls -la ~/.claude` should point to the claude-code-common repo's `claude/` directory
11. **Git hooks linked** — `git config --global core.hooksPath` should return `~/.git-hooks`
