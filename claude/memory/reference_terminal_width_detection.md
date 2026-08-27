---
name: Terminal width detection for full-width output
description: How to get the real Claude Code terminal width for width-bounded output, and why the obvious methods return a fallback instead
type: reference
---
Getting the user's real terminal width from inside a skill or tool is not straightforward, because the Bash/PowerShell tools run with a piped (non-tty) stdout:

- `shutil.get_terminal_size()` / `os.get_terminal_size()` → returns the fallback (80); stdout isn't a tty.
- `tput cols` or `powershell.exe ...` **launched from the Bash tool** → wrong value (the Bash pty is ~80, and a spawned `powershell.exe` gets its own ~120 console, not the real one).
- The **PowerShell tool** evaluating `$Host.UI.RawUI.WindowSize.Width` → **correct** real width (e.g. 156). The PS host object attaches to the actual console. This is the reliable Windows source. On macOS/Linux, `tput cols` / `$COLUMNS` is the best-effort equivalent.

**TUI gutter:** Claude Code indents message/tool output by ~2 columns, so a table or box exactly as wide as the window has its right border clipped off-screen. Subtract a ~2-column margin from the detected width when sizing full-width output.

Because the detection must happen outside the piped process, width-dependent rendering also can't live in a skill's `!` context line — that always renders at the fallback width. Detect the width in a process step, then pass it down.

**The PowerShell tool is not present in every session.** Observed 2026-08-26: a session had no PowerShell tool at all — absent from the tool list, and a `ToolSearch` for it returned no deferred match — which leaves *no* source of the real width, since every Bash route above is already ruled out. Don't burn turns hunting for a substitute; there isn't one. Pin the width in the consuming skill's own config instead: `github-status` reads a `GHS_WIDTH` line from `~/.claude/skills/github-status/config/config.env`, which sits ahead of detection in its fallback chain (`--width` → `GHS_WIDTH` env → config.env → detected width → 120).

Applied in the `github-status` skill: it detects the width (PowerShell tool), subtracts 2, and passes `--width N` to `repos-status.py`, whose DESCRIPTION column is elastic (fills the remaining width, wraps long text). See `claude/skills/github-status/SKILL.md` in the Claude dotfiles repo.
