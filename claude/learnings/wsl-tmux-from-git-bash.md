# Driving WSL tmux from Git Bash

Measured 2026-10-09/10 on Windows 11, Ubuntu under WSL 2, tmux 3.4, while chasing a
Claude pane that drew at 80 columns inside a wide tmux pane.

## Getting a command into WSL intact

- **Set `MSYS_NO_PATHCONV=1`** on every `wsl -d <distro> -- …` call that names a Linux path.
  Without it Git Bash rewrites `/tmp/x.log` into a Windows temp path before wsl.exe sees it:
  `cat: 'C:/Users/…/AppData/Local/Temp/x.log': No such file or directory`.
- **Do not pass shell variables through `wsl -- sh -c '…'` or `bash -c '…'`.** A loop variable
  arrived empty inside the inner shell even with the outer string single-quoted (`tmux set-hook
  -gu "$h"` → `ambiguous option:`; `capture-pane -t $s` → `-t expects an argument`). Write the
  script to a file under the repo's `tmp/` and run `wsl -d <distro> -- bash /mnt/<drive>/…/script.sh`.
  That was reliable every time.

## tmux hooks that log

```tmux
set-hook -g window-resized 'run-shell -b "echo \$(date +%H:%M:%S.%N) WINDOW #{session_name} #{window_width}x#{window_height} >> ~/tmux-size.log"'
```

- In a config file, `%` stays single. Doubling it (`%%H`) reaches `date` unchanged and prints a
  literal `%H:%M:%S.%N`.
- Escape the `$` of `$(date …)` so it runs when the hook fires. Set from `sh -c "…"` with an
  unescaped `$`, the date is expanded once at `set-hook` time and every line carries the same stamp.
- `window-resized` is a window hook: it shows under `tmux show-hooks -gw`, not `-g`, and is unset
  with `set-hook -gwu`.
- Hooks set at runtime die with the server; only `~/.tmux.conf` survives a reboot.
- Test hooks on a private server first: `tmux -L <name> -f <conf> new-session -d …`, then
  `tmux -L <name> kill-server`.

## Window size behaviour under `window-size latest` (the default)

- `new-session -d` with **no client attached anywhere** creates the window at `default-size`,
  80x24. With any client attached to the server, the window is created at the latest client's size.
- Detaching the last client leaves the window at its current size; it does not fall back to 80x24.
- A client attaching to a smaller window resizes it to the client's size. On boot, the window was
  resized within about 15 ms of `new-session -d`, before the program in it had started.
- To create the window at the calling terminal's size, pass `-x`/`-y` from `stty size`, which
  prints `rows cols` and fails when stdin is not a terminal. Do not use `tput cols`: with no
  terminal it answers terminfo's 80 (and `lines` 24) instead of failing, so a "no terminal, skip
  the flags" guard built on it never fires. Measured 2026-10-11 from a 137x41 pane and from a call
  with stdin at `/dev/null`.

## Windows programs inside a tmux pane

A Windows executable run from a pane (WSL interop) does receive the pane's resizes, including two
in 50 ms: a PowerShell loop printing `[Console]::WindowWidth` tracked 241→100→80→200 exactly.

Reading such a process's console size from outside did not work: PowerShell `AttachConsole(pid)`
succeeded, but `CreateFileW("CONOUT$")` returned an invalid handle. The size the program renders
at can be read off its output instead: `tmux capture-pane -p -t '=<session>:'` and measure the
length of a full-width rule line. A bare name matches by prefix; the target forms are under "Naming one session exactly in a pane-level command".

**Killing the tmux side ends the Windows child.** A `PING.EXE -t` started as a pane command was gone two seconds after `tmux kill-session` on that session (measured 2026-10-15), so the WSL interop proxy dying takes the Windows process with it. The test has to run inside one `wsl.exe` invocation: a tmux server started by a `wsl.exe` that then exits hands its Windows children to that invocation's job object, and they die with it before anything can be observed. A long-lived server has to be started from something that outlives the connection, which is why a session holder exists.

## `remain-on-exit` holds more than its value says (tmux 3.4)

**Never set `remain-on-exit` server-wide to keep failed panes.** Any non-zero value, `failed` included, keeps a pane whose pty reached EOF before tmux collected its exit status: `server_destroy_pane` in `server-fn.c` returns early on `remain_on_exit != 0 && !(flags & PANE_STATUSREADY)`, and the `failed` test (exit 0 destroys) runs only after the status arrives. If it never arrives, the pane sits dead with `pane_dead_status` and `pane_dead_signal` both empty, indefinitely. Observed 2026-10-15 on a cleanly exited `claude.exe` pane whose wrapper shell went unreaped; it could not be reproduced on demand. With the option off, tmux destroys the pane at EOF whether or not a status ever comes.

To keep only the panes that fail, let the pane mark itself as it exits: `{ cmd; } || { s=$?; tmux set-option -p remain-on-exit on; exit "$s"; }`. Inside a pane `tmux` finds the right server and pane through `TMUX`/`TMUX_PANE`, so no target is needed there; outside one, an untargeted `set-option -p` marks whatever pane tmux treats as current. A command that calls `exit` itself, or that `exec`s its last step, ends the shell before the `||` branch and bypasses the hold.

## Naming one session exactly in a pane-level command

| target | `has-session` / `kill-session` | `display-message -p` / `capture-pane` |
|---|---|---|
| `name` | prefix match | prefix match: with `cc-proj` absent, a lone `cc-proj-docs` answers |
| `=name` | exact | not resolved: `display-message` prints an empty value and exits 0, `capture-pane` fails `can't find pane` |
| `=name:` | — | exact: absent prints empty (display) or `can't find session` (capture) |

Measured 2026-10-15 on tmux 3.4. The `=name` row is the dangerous one: a `[ "$(display-message … '#{pane_dead}')" = 1 ]` test built on it decides every pane is alive and raises no error.
