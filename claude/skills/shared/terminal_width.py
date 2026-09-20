#!/usr/bin/env python3
"""The real terminal width, for skill helpers whose stdout is a pipe.

Every skill that renders a table or a wrapped listing needs the width of the window
the user is actually looking at, and every ordinary probe lies about it from inside a
skill helper. Claude Code captures a helper's stdout — through a Context `!` line or
the Bash tool — so `shutil.get_terminal_size()` and `tput cols` return their built-in
80-column default, `$COLUMNS` is 0 or empty, and /dev/tty is `device not configured`.
None of those fail loudly: they hand back a plausible number, which is why a listing
silently rendered at 80 in a 147-column pane.

The shell a helper runs in genuinely has no controlling terminal. The agent harness a
few process levels up does, and its winsize is the pane's, so walking up the parent
chain to the first ancestor with a tty and reading that tty's size answers the real
question. Measured 2026-09-19 in agterm: `tput cols` said 80, this said 147, the pane
was 147.

Windows is not covered. Its consoles are not ptys and `stty` cannot address one, so a
caller there still needs the PowerShell tool evaluating `$Host.UI.RawUI.WindowSize.Width`
and must pass the answer in explicitly — see `~/.claude/memory/reference_terminal_width_detection.md`.

Used by the `memo` and `github-status` helpers. Import it rather than re-deriving the
walk; the failure it prevents is invisible, so a second copy that drifts reports a
wrong width just as confidently as a right one.
"""

from __future__ import annotations

import os
import shutil
import subprocess

# The harness sits a handful of levels above the helper; the bound only stops a runaway
# walk if the chain is ever cyclic or ps starts answering something unexpected.
_MAX_ANCESTORS = 12


def _ancestor_tty_columns() -> int | None:
    """Columns of the nearest ancestor process's controlling terminal, or None.

    None means no ancestor has a tty — a pipe, a cron job, CI — which is a real answer
    and not a reason to substitute a guess. Callers pick their own default.
    """
    if os.name == "nt":
        return None
    pid = os.getpid()
    for _ in range(_MAX_ANCESTORS):
        try:
            fields = subprocess.run(["ps", "-o", "ppid=,tty=", "-p", str(pid)], capture_output=True, text=True).stdout.split()
        except OSError:
            return None
        if len(fields) < 2:  # a no-tty process still prints "??", so a short line means ps found nothing
            return None
        parent, tty = fields[0], fields[1]
        if tty.startswith(("tty", "pts", "console")):
            return _tty_columns(tty)
        try:
            pid = int(parent)
        except ValueError:
            return None
        if pid <= 1:
            return None
    return None


def _tty_columns(tty: str) -> int | None:
    for flag in ("-f", "-F"):  # BSD/macOS spells the device flag -f, GNU/Linux -F
        try:
            size = subprocess.run(["stty", flag, f"/dev/{tty}", "size"], capture_output=True, text=True).stdout.split()
            return int(size[1])
        except (OSError, IndexError, ValueError):
            continue
    return None


# Claude Code's TUI indents tool output by a couple of columns, so output rendered exactly
# as wide as the window has its right edge pushed off-screen — a table loses its border, and
# a wrapped line gets re-wrapped by the terminal. Detection returns the window, so the gutter
# comes off here. Outside Claude Code nothing indents the output and the full width is right.
GUTTER = 2


def terminal_columns(default: int) -> int:
    """Usable render width: the real terminal less the TUI gutter, else `default`.

    Detection sees the whole window, which is what a caller measuring the screen wants, so
    the gutter is subtracted here rather than by each skill — one place to be wrong instead
    of two. A caller who has already done its own subtraction should pass its width in
    explicitly and not call this.
    """
    detected = _ancestor_tty_columns()
    if detected is None:
        return shutil.get_terminal_size((default, 24)).columns
    return detected - GUTTER if os.environ.get("CLAUDECODE") else detected
