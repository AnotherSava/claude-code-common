# Driving WSL tmux from Git Bash

Measured 2026-10-09/10 on Windows 11, Ubuntu under WSL 2, tmux 3.4, while chasing a
Claude pane that drew at 80 columns inside a wide tmux pane.

## Getting a command into WSL intact

- **Set `MSYS_NO_PATHCONV=1`** on every `wsl -d <distro> -- …` call that names a Linux path.
  Without it Git Bash rewrites `/tmp/x.log` into a Windows temp path before wsl.exe sees it:
  `cat: 'C:/Users/…/AppData/Local/Temp/x.log': No such file or directory`.
  Any argument with a leading slash is taken for a path, not only real ones: `tmux send-keys -l
  /exit` typed `C:/Program Files/Git/exit` into a Claude Code composer (measured 2026-10-22), so
  a keystroke meant to end a session was sent to the agent as a prompt instead.
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

An absent session prints empty under `=name:` too, so test `has-session -t =name` before reading a format: an empty `#{session_created}` does arithmetic as 0, which reads as a very old session. On 2026-11-21 that reported an ended session as one that never drew.

## A server that stops drawing new panes

**Probe a fresh pane before trusting a server.** On 2026-11-20 the long-lived holder server (tmux 3.4, up nine days) stopped showing output from any pane created after about 17:20, while panes created earlier kept updating. A `new-session -d … "echo marker; sleep 300"` ran its command, since the pane moved on to `sleep`, but `capture-pane -p` stayed empty. The same test on a separate `-L` server showed the line at once. The cause was not found: it was not file descriptors (45 against a limit of 10240), a Claude update or a hook.

A session created during the stall opened as a blank alternate screen with the cursor at 1,0, and keys changed nothing. The Windows program in it was alive, and its console title still reached `#{pane_title}`.

**A passing probe does not clear a session created during the stall.** The server recovered by itself between 00:09 and 02:02 the next night, same pid, and fresh panes drew again. One session created inside the stall still showed a single character the next morning, beside sessions showing 30 or more lines. Restarting that one session fixed it. The dotfiles repo's remote-session check (`wsl/cc-session.sh`) tests both: a throwaway pane for the server, and a line count for the session being opened.

## Handing an attached client a command to run instead

**`detach-client -t <client-tty> -E '<command>'` replaces a client's view with a command run in the client's own process.** That keeps its terminal and its environment: a variable exported before `tmux attach` was still set inside the command (tmux 3.4, measured 2026-11-20 with a client attached under `script`). It is how a restart can make every open terminal wait and reattach, with nothing on the terminal's side changing. `list-clients -F '#{client_tty}|#{session_name}'` names the clients to hand it to.

## Driving tmux from a Windows program (no Git Bash in between)

Measured 2026-10-19/20 from a Rust GUI process and from Python `subprocess`, Windows 11, tmux 3.4.

- **`wsl.exe -e sh -c "<script>"` carries the script intact** when it is one argv element from a program (Rust `Command`, Python `subprocess` list form): tabs, `$var`, `$(…)`, single and double quotes all arrive as written. `-e` runs the command without the distro's login shell. The variable-loss trap above is Git Bash rewriting a command line, not wsl.exe.
- **wsl.exe's own errors go to stdout, UTF-16LE, unless `WSL_UTF8=1`** is in its environment. A missing distro gave exit 4294967295 with `There is no distribution with the supplied name.` on stdout and an empty stderr; without the variable the same text is NUL-interleaved. Read stdout when stderr is empty, or the reason a call failed is lost. tmux's own errors stay on stderr as UTF-8.
- **`tmux has-session -t =<name>`** exits 1 with `can't find session: <name>` on stderr for a missing session, and `no server running on …` with no server; exit 0 and no output when present.
- **`capture-pane -e -p` re-serializes SGR rather than echoing what the program wrote.** Faint is a standalone `\e[2m`, and turning attributes off comes back as `\e[0m` followed by the colours re-applied, so a parser must handle both `0` and `22` ending faint. Colour arguments ride in the same sequence (`38;2;R;G;B`, `38;5;N`), so a `2` inside one is a colour component, not faint.
- **A tmux pane title is the console title of the Windows program in it.** `SetConsoleTitleW` on a `claude.exe` started from a pane shows up as `#{pane_title}`, so `list-panes -a -F '#{session_name}\t#{pane_title}'` reads what a Windows-side writer set.
