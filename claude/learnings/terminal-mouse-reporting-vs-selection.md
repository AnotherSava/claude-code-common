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

**The tmux `mouse` option says nothing about this.** A server reporting `mouse off` under
`show-options -g mouse` sits happily beside a pane at `all=1`: tmux forwards the application's mouse
mode to the outer terminal whether or not tmux handles the mouse itself. So a pane running a bare
`sleep` reports `0,0,0` while every pane running the offending program reports `1,1,1` — that contrast
is the evidence, and tmux's own setting is not.

Outside tmux there is nothing to query. DEC private modes are terminal state, not something a sibling
process can read, so compare two panes or two sessions instead of looking for an interface.

## Claude Code requests it, and one variable turns it off

Setting `CLAUDE_CODE_DISABLE_MOUSE=1` stops Claude Code requesting any of it. Verified 2026-09-26
against `claude.exe` 2.1.283 by a matched pair of tmux sessions — same binary, same directory, same
server, differing only in that variable: without it `any=1 all=1 sgr=1`, with it `0,0,0`. The
neighbouring `CLAUDE_CODE_DISABLE_MOUSE_CLICKS` and `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN` sit in the
same terminal-features group.

The same day, 2.1.251 on macOS requested nothing while 2.1.283 on Windows requested 1003 and 1006, with
`"tui": "fullscreen"` set in the settings.json both machines share. So the request arrives with a
version rather than with a setting, and a terminal whose drag-select works today loses it at an update.

Values in the `env` block of `settings.json` do reach the session's process environment — a shell inside
it prints them. Whether they are read early enough to affect the TUI's mouse setup is a separate
question, and exporting the variable into the process directly is the fallback that is known to work.

**Crossing WSL to a native Windows `claude.exe` needs `WSLENV`.** A variable exported in the WSL shell
is not inherited by a Win32 child unless it is named there:

```sh
tmux new-session -d -s probe -e CLAUDE_CODE_DISABLE_MOUSE=1 -e WSLENV=CLAUDE_CODE_DISABLE_MOUSE -c <dir> <claude.exe>
```

The `-e` flag is also what keeps that line free of quotes and spaces, which matters when the command
travels through a Windows sshd — only bare tokens survive cmd.exe there.

## Bypassing it for one drag, or for every program

Hold **shift** while dragging to bypass the capture with no config change, and ⌘⇧-click for a link. A
program can claim shift for itself with `XTSHIFTESCAPE`; `mouse-shift-capture = never` in
`~/.config/agterm/ghostty.conf` makes shift always win.

Setting `mouse-reporting = false` in that same file turns reporting off for every program in agterm, so
selection and links always work — at the cost of mouse scrolling in tmux and click-to-position in vim.

**Prove a config key exists before believing a silent reload.** A run of `agtermctl config reload`
prints a diagnostic count, and `0` is what a valid key and a quietly ignored line look like alike until
a control separates them: a deliberately bogus `mouse-reporting-bogus` raised the count to 1 where
`mouse-reporting` left it at 0.
