---
name: reference-terminal-width-detection
description: How to get the real Claude Code terminal width for width-bounded output (and the TUI gutter)
metadata: 
  node_type: memory
  type: reference
---

Getting the user's real terminal width from inside a skill/tool is not straightforward, because the Bash/PowerShell tools run with a piped (non-tty) stdout:

- `shutil.get_terminal_size()` / `os.get_terminal_size()` → returns the fallback (80) — stdout isn't a tty.
- `tput cols` or `powershell.exe ...` **launched from the Bash tool** → wrong value (the Bash pty is ~80; a spawned `powershell.exe` gets its own ~120 console, not the real one).
- The **PowerShell tool** evaluating `$Host.UI.RawUI.WindowSize.Width` → **correct** real width (e.g. 156). The PS host object attaches to the actual console. This is the reliable Windows source. On macOS/Linux, `tput cols` / `$COLUMNS` is the best-effort equivalent.

**TUI gutter:** Claude Code indents message/tool output by ~2 columns, so a table/box exactly as wide as the window has its right border clipped off-screen. Subtract a ~2-column margin from the detected width when sizing full-width output.

Applied in the `github-status` skill: it detects the width (PowerShell tool), subtracts 2, and passes `--width N` to `repos-status.py`, whose DESCRIPTION column is elastic (fills the remaining width, wraps long text). See `claude/skills/github-status/SKILL.md`.
