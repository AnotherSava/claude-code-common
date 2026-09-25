# Keeping a terminal session alive on a Windows box you reach over SSH

Unless a section gives a date or setup of its own, what it describes was measured against a Windows
11 machine (build 10.0.26200) driven from a Mac over Tailscale SSH, on 2026-09-21. The worked case is a Claude Code session that has to survive
disconnects and be viewable from two machines at once, but the failures are not specific to it: they
hit any long-lived process started on a Windows host through an SSH connection.

The SSH mechanics themselves — quoting through cmd.exe, the admin-key trap, probing reachability —
are in [[windows-openssh-over-tailscale]]. Task registration without admin rights, and the two
defaults that silently defeat a task, are in [[windows-scheduled-tasks-nonadmin]].

## Everything an SSH session starts is killed when the connection drops

A node ticker appending a UTC timestamp to a log every 5 s, started with `start "" /b` from an `ssh`
command, wrote exactly one line — the one at t=0, while the connection was still up — and nothing in
the following 70 s.

This is Win32-OpenSSH's job object with Kill-on-Job-Close, and `start /b` does not escape it. Nothing
about the symptom says so: the process starts, does its first unit of work, and is simply gone, with
no error anywhere and no exit status to read.

**A scheduled task escapes it.** The identical ticker launched via `schtasks /create … /sc once`
plus `schtasks /run` kept appending across a 70 s disconnect, unbroken.

## Choose the Windows session deliberately, because sshd is in session 0

The scheduled task above ran in **Console session 1** — the interactive desktop session — not
session 0, where sshd lives. That difference decides what the hosted process can do: session 0 has no
access to the interactive desktop, so an agent hosted there can build and unit-test a Windows GUI
application but cannot show it on screen or drive its GUI.

Where desktop access is the point, the holder belongs in the interactive logon session. The costs are
real and worth stating up front: logging off ends it, and an at-logon trigger is what recovers a
reboot. `-LogonType S4U` ("run whether the user is logged on or not") is not the escape hatch it
looks like — it requires elevation and gets a restricted token with no access to network resources.

## WSL idle-shuts the distro down and takes everything inside it

A detached tmux session created over ssh was still listed by a second ssh a moment later. 45 s after
the last connection closed, `wsl --list --running` reported "There are no running distributions" and
the tmux server was gone with it.

Two settings and one mechanism apply, and only the mechanism is reliable:

- `[general] instanceIdleTimeout = -1` in `%USERPROFILE%\.wslconfig` is documented as disabling the
  distro-level auto shutdown. This one is worth setting.
- `[wsl2] vmIdleTimeout` is documented as a millisecond count with **no documented disable value**.
  Do not write `-1` there and assume it means the same thing as the key above.
- What actually holds the VM is a blocking foreground command inside it — a `sleep infinity` run
  through `wsl.exe` by the scheduled task. That is a live connection for as long as the task runs, so
  the VM is never idle and the timeout never has a chance to fire.

Measured with the holder in place: distro uptime kept climbing across repeated disconnects, and
`wsl --list --running` still listed it.

## A Windows process launched through WSL interop inherits the launcher's job object

This is the finding that costs the most to discover, because every visible part of the system stays
healthy while the thing you care about dies.

With the holder above running, a tmux session was created **over ssh**, hosting a native Windows
`claude.exe` with its working directory on `/mnt/d`. It rendered correctly. After a 150 s disconnect:

| what | state |
| --- | --- |
| WSL distro | up, 6 min uptime, never restarted |
| holder process | alive |
| `claude.exe` | **gone** |
| tmux server | **gone** |

A Windows process started through WSL interop joins the job object of the `wsl.exe` that began its
WSL session — so a tmux **server** forked from an ssh connection hands every Windows child inside it
to that connection. When the connection dropped, `claude.exe` was killed, its tmux window closed, the
last session ended, and the server exited behind it. The distro survived because a different process
was holding it, which is exactly what makes the failure read as unrelated to the connection.

**The server has to be created by the out-of-band holder, not by the connection that creates a
session.** A `tmux new-session` issued later over ssh then talks to that existing server over its
socket, and the *server* forks the pane — so the Windows child belongs to the scheduled task.
Measured after the change: the same session survived a 150 s disconnect with `claude.exe` alive and
its prompt intact.

Anything that creates sessions should refuse when the holder's server is absent rather than starting
its own. A session started against a fresh server looks identical and works perfectly until the
connection drops.

## A tmux server with no sessions does not stay up

`tmux start-server` starts a server that exits again immediately, because it holds no sessions. A
holder that runs it and then sleeps looks like it is keeping a server alive and is not — and the
failure surfaces later, as `no server running on /tmp/tmux-1000/default`, from whatever tries to
attach.

Hold it with a session instead: `tmux new-session -d -s _holder 'sleep infinity'`. Assert on
`tmux has-session`, never on `pgrep -x tmux` — the server's process name is `tmux: server`, so an
exact-name match never finds it and reports a healthy server as absent.

## A script running over the drvfs mount locks the file on the Windows side

A Linux process executing a script from `/mnt/<drive>` holds an open Windows file handle for as long
as it runs. Anything that rewrites that path then fails:

```
scp: dest open "D:/.../holder.sh": Failure
```

A `git pull` on the Windows side fails the same way, naming the file and not the reason — which is
the expensive version, because the repo is where a long-running script naturally lives.

Copy such a script into the distro's own filesystem at install time and point the task at the copy.
The cost is that editing the repo copy changes nothing until the installer runs again, so say that in
the script itself.

## `wslpath` loses its backslashes when it is handed a Windows path from PowerShell

```
wslpath: D:projectsclaudeclauderemote-sessionwslholder.sh
```

The path is consumed by PowerShell and `wsl.exe` argument parsing before `wslpath` ever sees it.
Build the `/mnt/<drive>/…` form yourself from a configured value rather than converting a Windows
path at the boundary.

## The pty chain works, and the trap is on the local side

- **A real Linux pty reaches inside WSL through the Windows sshd.** Running `tty`, `tput cols` and
  `tput lines` through `ssh -tt <host> "wsl -d <distro> -- …"` returns `/dev/pts/0`, the real column
  and row counts, and `TERM=xterm-256color`.
- **It only looks right when the *local* side also has a pty.** Without one, conhost's screen-clear
  swallows the output and the command appears to do nothing. Drive it with `script -q /dev/null ssh …`
  or a `pty.fork()` harness. A first attempt was misread as "the pty path is broken" for exactly this.
- **A native Windows process launched from inside WSL gets a real TTY.** `node.exe` run that way
  reports `process.stdout.isTTY = true`, `process.stdin.isTTY = true` and a correct column count.
- **Resize propagates with a race.** On a mid-session `TIOCSWINSZ` the far side's `WINCH` trap fires
  while `stty size` still reports the OLD size; a later read is correct. conhost also injects an
  `ESC[8;rows;cols t` sequence into the stream. Expect a beat of lag and a redraw.

## An environment variable reaches a Windows child only if `WSLENV` names it

Exporting a variable in the Linux shell is not enough — WSL passes through only what `WSLENV` lists.
Measured with the same variable both ways:

```
export VAR=1; export WSLENV=VAR:$WSLENV;  cmd.exe /c echo %VAR%   ->  1
export VAR=1;                             cmd.exe /c echo %VAR%   ->  %VAR%
```

The failure is quiet in the direction that matters: the Windows side sees the variable as unset and
takes its default, which for a feature flag means the feature silently stays on. Run the control —
the literal `%VAR%` coming back is what proves the first result was `WSLENV` doing its job.

## Keep the sources on the Windows drive, not in ext4

With the WSL working directory on `/mnt/d/projects/<name>`, a Windows child reports
`process.cwd() === "D:\\projects\\<name>"` — a native path, not a UNC one. That is why sources have
to stay on the Windows drive: a Windows toolchain invoked from an ext4 working directory gets the
`cmd.exe` "UNC paths are not supported" failure.

It is also why the agent is a Windows process rather than a WSL one. Anthropic's own troubleshooting
documents that on WSL across filesystems Claude's Search "returns fewer results than on a native
filesystem" while `claude doctor` still reports Search as OK — a silent correctness hazard for
grep-driven reasoning.

## tmux serves several clients; `claude attach` serves one

- **`claude attach` is single-viewer.** With one client attached, a second attach caused the first to
  print `Session opened in another window` and exit; the second took over. The hand-off is clean, not
  a hang — which makes it easy to mistake for a crash on the first client.
- **tmux takes both.** Two simultaneous clients on one session, each on its own SSH connection, both
  `attached,focused`; neither was kicked.
- **A shared pane is clamped to the smallest attached client.** With one client at 120 columns and
  one at 200, both draw at 120.
- **A detached session is created at tmux's 80x24 default** and a TUI draws itself once at that size.
  Pass `-x`/`-y` at creation so the first attaching client does not inherit a layout built for a
  terminal nobody is using.

So where one viewer is enough, `claude --bg` plus `claude attach` needs no WSL, no tmux and no
scheduled task, and is by far the shorter path. Everything above is the price of the second viewer.

## Nothing on a tmux client says which machine it is on

Two clients on one server — one opened from a Windows terminal on the box, one over SSH from a Mac —
are indistinguishable by every ambient signal. Measured 2026-09-22 against both at once, with the
origin of each known in advance:

| Signal | Why it does not answer |
|---|---|
| tmux's own `client_*` variables | Both `client_uid` and `client_user` name the same WSL user, because SSH lands in it. The `client_tty`, `client_name` and `client_pid` values are allocation order. The one informative variable, `client_termtype`, carries the emulator's XTVERSION reply — it names the terminal program, not the machine, and is empty for one that does not answer. |
| The client's `/proc/<pid>/environ` | No `SSH_CLIENT`, `SSH_CONNECTION` or `SSH_TTY` reaches it: `wsl.exe` re-enters the distro with a clean environment and the remote's `WSLENV` is empty. The differences that do exist name the wrapper script that attached, not the machine it ran on. |
| WSL process ancestry | Token-identical on both: `tmux: client` → `Relay(<pid>)` → `SessionLeader` → `/init` → `systemd`. |
| The Windows process tree | It does separate them — the remote's `wsl.exe` descends from a per-connection `sshd.exe`, the local one from the terminal — but a Windows process and a WSL tmux client share no identifier to join them by. A timestamp join picked the wrong tree on the live data: the remote client's `client_created` read a second *earlier* than the `sshd.exe` that caused it. |

So the origin has to be stated by whatever attaches, and read back from the client's own environment.
Export a variable naming the machine before running `tmux attach-session`, then read
`/proc/<client_pid>/environ` for the pids `tmux list-clients -t "=<session>"` reports. That storage
holds: an environment set before the attach is still readable on the client pid hours later, mode
0400 and owned by the same user, from a process that is not its descendant.

Two traps in doing it. A wrapper both machines share cannot state the origin — each entry point has
to pass the machine as an argument rather than the reader inferring it from which script ran, or a
local call into the shared wrapper gets stamped remote. And a client that recorded nothing is not
evidence of "somewhere else": it is equally one attached before the convention shipped, one attached
by driving tmux by hand, and one whose `/proc` entry could not be read.

## Putting a status on every terminal attached to a session

A status an outside process writes into the session — the Claude Code Dashboard titling a tab — has
to cross tmux to reach the terminals, and by default it stops there. Measured 2026-09-24 against
tmux 3.4 in WSL, with every tab reading `PowerShell` while the dashboard logged each write as
successful:

- **A Windows child's console title becomes the pane's title.** `claude.exe` in a pane runs on a
  headless conhost under `wslhost.exe`. A `SetConsoleTitleW` issued through `AttachConsole` on it
  arrives as `#{pane_title}`, and so do the program's own title escapes. At start the pane title is
  the executable's Windows path, not the host name a Linux pane gets.
- **tmux passes a pane title on only with `set-titles on`.** With `set-titles-string '#T'` it arrives
  byte for byte, emoji, `%` and `#{…}` included. The default string puts `#S:#I:#W - ` in front of
  it. A client is sent the title of the pane in front of it, only when that changes, so a change in
  a session it is not viewing never reaches it.
- **A title format is expanded per client, and reads flags but not environment.** `client_flags`
  and `client_termname` differ per client; the client's environment is invisible to formats.
  `attach-session -f active-pane` works as a marker, and does nothing in a one-pane window:
  `#{?#{m:*active-pane*,#{client_flags}},⇄ #T,#T}` gave two clients of one session `⇄ 🟢 x` and
  `🟢 x`.
- **An export in the shell that runs `new-session` never reaches the pane** when the server is
  already running. The pane gets the server's environment plus only the variables
  `update-environment` names. Put the export in the pane's command, and add it to `WSLENV` there
  for a Windows child (see the `WSLENV` section above).
- **Windows Terminal keeps the last title after a detach.** tmux pushes and pops the title around an
  attach (`CSI 22;0;0t` and `CSI 23;0;0t`, from the `xterm-256color` smcup/rmcup), and Windows
  Terminal implements no title stack ([microsoft/terminal#14575](https://github.com/microsoft/terminal/issues/14575)).
  Attach without `exec` and print an empty `OSC 0` when tmux returns.
- **Windows OpenSSH's ConPTY forwards the titles to the ssh client**, after first sending its own
  console title (`C:\WINDOWS\SYSTEM32\cmd.exe`). Measured in a private ConPTY harness driving the
  same `cmd.exe /c wsl … tmux attach` the sshd runs, not on the Mac itself.
- **tmux stores `.` and `:` in a session name as `_`.** A script that derives a name keeping them
  misses the session on every later `=name` lookup.

## The Mac-as-host direction needs almost none of this

Reaching a session on the *Mac* from a Windows terminal is the same idea and a far smaller build,
because every heavy piece above exists to defeat one Windows behaviour. The holder, the scheduled
task, the WSL keepalive and `.wslconfig` are all downstream of Win32-OpenSSH's job object killing
whatever an SSH connection started. macOS has no equivalent, so a tmux server started over SSH there
is expected to outlive the connection with nothing holding it open.

Measured 2026-09-23: an `ssh … whoami` run from the Windows box into the Mac account authenticated on
a key already in place and returned that account's own name. So the transport is in place in both
directions, and an earlier reading that called this one closed had used the *Windows* account name
against the Mac — the two machines name their accounts differently, and the wrong user draws the
same `Permission denied (publickey)` a missing key does. Take the account and host from the
machine-coordinates memory rather than from here; naming them in this file would publish them.

What is actually missing on the Mac is smaller and duller: tmux is not installed, and nothing starts
Claude inside it, so no session there is attachable by anything. That is the same state the Windows
box was in before any of this was built — a Claude owning its terminal's own pty, which no second
client can join.

The survival claim is reasoned from the absence of job objects rather than measured, because there
is no tmux on that machine to measure it with. Test it before relying on it.

## Still unmeasured

- Whether a tmux server started over SSH on macOS survives the connection dropping. Reasoned above
  from the absence of a job object, never run.
- Survival across a Windows reboot, a Windows Update restart, and a logoff. Only the at-logon trigger
  was reasoned about; none of the three was tested.
- Whether `SIGWINCH` reaches the *Windows* console child through the WSL interop relay on a
  mid-session resize. The measurement above covers the client→WSL leg only.
- Ctrl-C, bracketed paste and mouse reporting through the interop relay.
- Whether an ssh-started `claude --bg` escapes the job object on a box with no daemon already
  running.
- Whether a pane's title reaches an agterm tab end to end over Windows OpenSSH from the Mac, `⇄`
  included, and whether the Mac's own dashboard then leaves that tab alone. The ConPTY leg was
  measured in a local harness on the Windows machine only.
