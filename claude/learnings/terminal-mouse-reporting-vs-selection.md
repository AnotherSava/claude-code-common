# Mouse reporting takes selection away from the terminal

A drag that always selected text stops selecting and ⌘C copies nothing — no error, no log line, and the
tab next to it still works. The terminal is not at fault: a program inside it turned mouse reporting on,
so the drag is delivered to that program as mouse events instead of becoming a selection the terminal
owns. In libghostty ⌘-hover link detection goes at the same moment, the pointer stays a text bar, and
⌘-click opens nothing; all of it comes back when that program exits.

## Read the mode, do not infer it

Inside tmux the pane's requested modes are readable, which makes the diagnosis a measurement rather
than a theory:

```sh
tmux display-message -p -t <session> any=#{mouse_any_flag},all=#{mouse_all_flag},sgr=#{mouse_sgr_flag},cmd=#{pane_current_command}
```

A pane answers `any=1` when its program asked for tracking at all, `all=1` for DECSET 1003 (any-event)
and `sgr=1` for the 1006 encoding.

**The tmux `mouse` option does not tell you what the pane asked for.** A server reporting `mouse off`
under `show-options -g mouse` sits happily beside a pane at `all=1`: tmux forwards the application's
mouse mode to the outer terminal whether or not tmux handles the mouse itself. So a pane running a
bare `sleep` reports `0,0,0` while every pane running the offending program reports `1,1,1` — that
contrast is the evidence, and tmux's own setting is not.

**Keep `mouse off` anyway: `mouse on` requests the mouse itself.** With it, tmux sends `[?1002h` to
the outer terminal whether or not any pane wants the mouse, so the outer terminal loses plain
drag-select and its own wheel scrollback even with every program's reporting off. With `mouse off`,
tmux writes outward only what the pane requested. Measured 2026-10-01 on the Windows box through
agwinterm; not checked on macOS.

Outside tmux there is nothing to query. DEC private modes are terminal state, not something a sibling
process can read, so compare two panes or two sessions instead of looking for an interface.

## Claude Code requests it, and two variables choose how much

Claude Code has three mouse modes, and two variables pick between them:

- **full** — the default: DECSET 1003 and 1006, so every drag goes to Claude.
- **scroll** — `CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1`: only 1000 and 1006, never 1002 or 1003. The wheel
  still scrolls Claude's transcript, and a terminal that keeps drags for itself when no motion is
  tracked still selects. This is what the shared `settings.json` sets.
- **off** — `CLAUDE_CODE_DISABLE_MOUSE=1`: nothing requested, so the wheel stays with the terminal and
  never scrolls the transcript. On the alternate screen there is no scrollback for it either, and what
  the terminal does with it instead is the next section.

The off mode was verified 2026-09-26 against `claude.exe` 2.1.283 by a matched pair of tmux sessions
— same binary, same directory, same server, differing only in that variable: without it `any=1 all=1
sgr=1`, with it `0,0,0`. The scroll mode was measured 2026-10-01 on the Windows box through agwinterm
with tmux `mouse off`, which wrote outward exactly `[?1006h [?1000h`; not checked on macOS.

**Delete `CLAUDE_CODE_DISABLE_MOUSE` to use scroll mode; setting it to `"0"` gives full mode.** The
variable is tested for presence, not truth — `if (CLAUDE_CODE_DISABLE_MOUSE !== undefined) return
value ? "off" : "full"` — so any value, `"0"` included, decides the mode and `DISABLE_MOUSE_CLICKS` is
never read. That comes from reading the minified `claude.exe` source on 2026-10-01, not from a
matched run.

The same day, 2.1.251 on macOS requested nothing while 2.1.283 on Windows requested 1003 and 1006, with
`"tui": "fullscreen"` set in the settings.json both machines share. So the request arrives with a
version rather than with a setting, and a terminal whose drag-select works today loses it at an update.

The `env` block of `settings.json` is early enough, so the flag belongs there rather than in a launcher.
Measured the same day on the Windows box: a session whose only source of the variable was the
checked-out `settings.json` — no shell export, no `WSLENV` — reported `0,0,0`, where the identical
command before that file carried the flag reported `1,1,1`.

**Restart a running session after changing these variables; the change does not reach it.** When the
shared `settings.json` swapped `CLAUDE_CODE_DISABLE_MOUSE` for `CLAUDE_CODE_DISABLE_MOUSE_CLICKS` on
2026-10-01, a session started the day before ended up carrying both in its process environment: the
reload added the new key and never removed the old one. Because the old one is tested for presence,
that session stayed in off mode, and its pane still reported `0,0,0` while two sessions started after
the change reported `any=1 std=1 sgr=1`. So when one session's wheel misbehaves and its neighbours' do
not, compare each pane's start time with the date of the last mouse-related change to `settings.json`.

**Crossing WSL to a native Windows `claude.exe` needs `WSLENV`.** A variable exported in the WSL shell
is not inherited by a Win32 child unless it is named there:

```sh
tmux new-session -d -s probe -e CLAUDE_CODE_DISABLE_MOUSE=1 -e WSLENV=CLAUDE_CODE_DISABLE_MOUSE -c <dir> <claude.exe>
```

The `-e` flag is also what keeps that line free of quotes and spaces, which matters when the command
travels through a Windows sshd — only bare tokens survive cmd.exe there.

## The wheel on the alternate screen, when nobody asked for it

The wheel scrolls Claude Code's transcript only in full or scroll mode. With the mouse off and the app
on the alternate screen, neither side owns the wheel, and terminals disagree about what happens:

- **Windows Terminal turns it into arrow keys** — xterm's alternate scroll mode, DECSET 1007, sending
  `ESC O A` / `ESC O B` one line per notch with no setting to tune or disable it. Claude Code reads
  those as Up/Down, so the wheel walks the input history. Read on 2026-10-01 from Windows Terminal's
  `TerminalInput::_makeAlternateScrollOutput` and microsoft/terminal#3321, not reproduced by a run.
- **agterm turns it into arrow keys too.** On 2026-10-01 the user saw the trackpad walk Claude's input
  history in a remote tmux pane whose Claude had requested nothing, viewed from agterm on the Mac.
  That was the user's report, not a matched comparison of two panes. The shipped binary's strings
  contain `mouse-reporting`, `mouse-scroll-multiplier` and `mouse-shift-capture` but no
  `alternate-scroll` key, so assume no ghostty setting turns this off until someone finds one.
- **agwinterm drops it.** Its wheel handler returns early when `IsAltScreen` is set, and its mode
  switch handles 1000, 1002, 1003, 1006 and 1016 with no 1007 case.

So "the wheel scrolls history in Windows Terminal or agterm and does nothing in agwinterm" is this one
mode, and none of them is transcript scrolling. Adding 1007 to agwinterm would reproduce the Windows
Terminal behaviour, not fix it. The fix is on the pane's side: a Claude in scroll mode.

## Bypassing it for one drag, or for every program

Hold **shift** while dragging to bypass the capture with no config change, and ⌘⇧-click for a link. A
program can claim shift for itself with `XTSHIFTESCAPE`; `mouse-shift-capture = never` in
`~/.config/agterm/ghostty.conf` makes shift always win.

On Windows, agwinterm's left-button handler skips forwarding while Shift is held, so Shift+drag
selects under any mode. Upstream agwinterm forwards a plain press whenever reporting is on, which in
scroll mode sends the drag to Claude, where it is discarded. The user's fork patches that handler to
forward only when the app tracks motion (1002/1003), so under scroll mode a plain drag selects too.

Setting `mouse-reporting = false` in agterm's config file turns reporting off for every program in agterm, so
selection and links always work — at the cost of mouse scrolling in tmux and click-to-position in vim.

**Prove a config key exists before believing a silent reload.** A run of `agtermctl config reload`
prints a diagnostic count, and `0` is what a valid key and a quietly ignored line look like alike until
a control separates them: a deliberately bogus `mouse-reporting-bogus` raised the count to 1 where
`mouse-reporting` left it at 0.
