# Redrawing a status block in place from a shell script, and testing it without taking the screen

A status that repeats every few seconds belongs in one block the script redraws, so the newest state is always the
bottom of the terminal. `claude/remote-session/mac/attach.sh` does this for its reconnect loop (`status_draw`,
`status_end`), in POSIX `sh` under `set -eu`.

## The redraw

- **Count rows, not lines.** Before redrawing, the cursor climbs back over everything the last drawing printed with
  `\r\033[<n>A\033[J`. A line wider than the terminal fills more than one row, so `n` is the sum over lines of
  `ceil(length / columns)`, with the width read at drawing time (`tput cols`) since the window can be resized between
  drawings. Too small an `n` leaves the old block above the new one; too large an `n` erases one line of earlier
  output on every redraw, so the block creeps up the screen.
- **`${#var}` counts characters only under a UTF-8 locale.** Elsewhere it counts bytes, so a `⇄` or `—` makes a line
  look longer than it is. That changes `n` only when the miscount crosses a multiple of the width, so a block of short
  lines is safe and a line near the full width is not.
- **Keep the countdown on its own unterminated line** and rewrite it with `\r\033[K`. The block's row count then
  covers only the lines above it, and the next drawing climbs from the start of the countdown line.
- **Anything printed below a drawn block must end it first** (a newline, and zeroing the row count). Otherwise the next
  drawing climbs over that output and erases it.
- **Turn echo off from the countdown through the next attempt** (`stty -echo`, restored once that attempt returns and
  before anything interactive runs). A typed Enter adds a row the count does not know about, and the next redraw lands
  one row too low; restoring it when the wait ends leaves the attempt itself, up to a full connect timeout, open to that.
- **Tick against a wall-clock deadline** (`date +%s`), not by summing `sleep` durations. A wait that spans a system
  sleep then ends on waking instead of running its full length afterwards.

## A program that leaves a terminal mode on

When an ssh session running tmux dies, nothing turns off the modes the far side enabled. The script resets the
alternate screen (`\033[?1049l`) for that reason, and also needs focus reporting off (`\033[?1004l`). With focus
reporting left on, every return to the tab makes the terminal send `ESC [ I`, which the tty echoes as `^[[I` under the
status. This was inferred from a screenshot showing that sequence after a dropped attach and has not been reproduced.

## Testing it without driving the real terminal

Run the script under `pty.fork()` at a fixed size (`TIOCSWINSZ`), feed every byte it writes into a `pyte.Screen` of
the same size, and print `screen.display` at chosen moments. That renders the cursor movement and erasing as a terminal
would, so a duplicated block, a creeping block or a stale countdown shows up in the snapshot. It needs no window and
no keystrokes, so the machine-takeover ask does not apply. Install `pyte` in a throwaway venv, and strip `AGTERM_*`
from the child's environment, since an agterm-aware script otherwise acts on the session that launched the test.

To reach a retry loop that normally requires a session to have connected first, test a scratch copy with that
precondition flipped and the timeouts shortened, pointed at a TEST-NET address such as `192.0.2.1`, which times out
instead of refusing.
