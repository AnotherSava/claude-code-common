---
name: Terminal width detection for full-width output
description: Skill helpers get the real width from skills/shared/terminal_width.py; why every obvious probe returns a plausible fallback instead, and what is still Windows-only
type: reference
---
Width-bounded output — a table, an aligned listing — is sized by `claude/skills/shared/terminal_width.py`. Import `terminal_columns(fallback)` from it rather than writing a detector; the argument is what to use when nothing can be detected.

Getting the real width from inside a skill helper is not straightforward, because the Bash/PowerShell tools run with a piped (non-tty) stdout, and **every probe fails by returning a plausible number rather than an error**:

- `shutil.get_terminal_size()` / `os.get_terminal_size()` → its own fallback (80); stdout isn't a tty.
- `tput cols` → 80. Measured 2026-09-19 on macOS in a 147-column pane. Previously believed to be the best-effort macOS/Linux source; it is not, and it is no better there than the Git Bash case below.
- `$COLUMNS` → `0` or empty.
- `/dev/tty` → `device not configured`. The helper's shell has no controlling terminal at all.
- `powershell.exe` **launched from the Bash tool** → its own ~120 console, not the real one.

**What does work on macOS/Linux:** the shell has no tty, but the Claude Code process a few levels up does, and its winsize is the pane's. Walk `ps -o ppid=,tty=` up the parent chain to the first ancestor with a tty, then read `stty -f /dev/<tty> size` (`-F` on GNU/Linux). That is what the shared module does — 147 where `tput cols` said 80.

**Windows is still PowerShell-only.** A console is not a pty, so the walk finds nothing. The **PowerShell tool** evaluating `$Host.UI.RawUI.WindowSize.Width` attaches to the actual console and returns the real width; the consuming skill subtracts the gutter itself and passes `--width N`. Keep `--width` honored ahead of detection for exactly this.

**TUI gutter:** Claude Code indents message/tool output by ~2 columns, so content exactly as wide as the window has its right border clipped off-screen. `terminal_columns` already subtracts this when `CLAUDECODE` is set, so a caller passing an explicitly detected width is the only one that needs to do its own subtraction.

**Context `!` lines still can't render width-dependent output** — they capture with no ancestor tty in reach, so they always come out at the fallback. Render in a process step instead.

**The PowerShell tool is not present in every session.** Observed 2026-08-26: a session had no PowerShell tool at all — absent from the tool list, and a `ToolSearch` for it returned no deferred match. On Windows that leaves no source of the real width; don't burn turns hunting for a substitute. Pin it in the consuming skill's config instead: `github-status` reads a `GHS_WIDTH` line from its `config/config.env`, which sits ahead of detection in its chain (`--width` → `GHS_WIDTH` env → config.env → detected width → 120).

Applied in `github-status` (a bordered table whose DESCRIPTION column is elastic, filling the remaining width) and `memo` (a wrapped, aligned listing). The authoring rule for new skills is the "Full-width terminal output" section of `claude/skills/skill/SKILL.md`.
