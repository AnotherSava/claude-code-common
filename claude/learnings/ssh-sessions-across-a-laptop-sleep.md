# Long-lived ssh sessions across a laptop sleep

A terminal tab holding `ssh` into another machine does not die when the laptop sleeps. It dies
hours later, at a moment nothing else explains, with a message that blames the far end. Every part
of that is misleading, and the companion file for the sleep itself is
`macos-idle-sleep-diagnosis.md`; this one is about what the sleep does to the sockets.

## The shape

Measured 2026-10-03, three ssh tabs from a MacBook Air into a Windows desktop over Tailscale, each
running `tmux attach` onto a long-lived session there:

| | |
|---|---|
| Mac unplugged from mains | 08:15 (on AC the profile was `sleep 0`, never) |
| Idle sleep | 08:26:52 |
| Last packet on the busiest flow | 08:26:51, one second earlier |
| ssh #1 dies | **09:41:31** — `CONNRESET`, `SO_ERROR: 0` |
| ssh #2 dies | **14:35:22** — `TIMEOUT`, `SO_ERROR [60: Operation timed out]` |
| ssh #3 dies | **15:00:57** — same |
| First full wake | 15:31:51 |

So: one event at the start, three deaths spread over 5h19m, two different errnos, and all of them
**before** the machine fully woke. The connections had been open since the previous afternoon and
had already survived many display sleeps.

Three readings that look obvious and are wrong:

- **"Closed by remote host" is the client's own wording for a local failure.** Two of those three
  sockets never received anything at all; ssh printed that line after its own `read()` returned
  nothing. Take the errno from the log, not the text on screen.
- **They did not all drop together.** Nothing happened at any of the three death moments. The
  sleep is the cause and none of the timestamps is near it.
- **The tunnel did not go down.** Tailscale had not restarted on either end, and a *fresh* TCP
  connection to the same host opened successfully at 13:29 and was still established — while two
  of the three ssh sockets sat dying.

## Why hours, and why at different times

Nothing was asking. Check all three clocks rather than assuming any of them:

```bash
ssh -G <host> | grep -iE 'serveralive|tcpkeepalive'   # client: serveraliveinterval 0 by default
sysctl -n net.inet.tcp.keepidle net.inet.tcp.keepintvl net.inet.tcp.keepcnt   # macOS: 7200000 ms
```

```powershell
# on the far side, the EFFECTIVE config, not the file
& "C:\Program Files\OpenSSH\sshd.exe" -T | findstr /i "clientalive tcpkeepalive"
```

OpenSSH ships `ServerAliveInterval 0` and `ClientAliveInterval 0`; the OS keepalive underneath is
two hours on macOS and the same by default on Windows. With no application-level probe, an idle
socket is only reaped when some OS timer that started at an unrelated moment finally fires — which
is exactly why three connections with the same cause died 5h19m apart in two different ways.

## Reading it back afterwards

**macOS keeps per-process socket events in the unified log**, and each ssh process records its own
failure with the errno and the connection's total duration — which back-solves to when it was
opened:

```bash
log show --predicate 'process == "ssh"' --start '2026-10-03 00:00:00' --style compact \
  | grep -iE 'CONNRESET|TIMEOUT|SO_ERROR|Duration'
```

That is the instrument. `pmset -g log` gives the sleep; this gives the deaths; the two together are
the whole story, and neither alone is.

**An absent disconnect record on the server proves nothing.** Windows' `OpenSSH/Operational` log
writes a termination line only when the client sends a clean SSH disconnect, so every abruptly
dropped session is an `Accepted publickey` with nothing after it. Reading the silence as "the
server never noticed" is a real trap — one of the three above had in fact been reset *by* that
server's TCP stack. Count the pairs before drawing anything from a gap:

```powershell
Get-WinEvent -FilterHashtable @{LogName='OpenSSH/Operational'; StartTime=(Get-Date).AddDays(-7)} |
  ForEach-Object { ($_.Message -split "`r?`n")[0] }
```

**Remember who the process-tree parent is.** Inside WSL, every `wsl.exe` invocation's Linux-side
relay is parented at `/init` → pid 2, so an ancestry walk from a tmux client always dead-ends there
whatever started it, and that looks exactly like an orphan. The real parent is on the Windows side.
Confirm whose a client is from its own environment instead — if the attach recorded one, e.g.
`tr '\0' '\n' < /proc/<pid>/environ | grep ORIGIN`.

## Two traps for a reconnect loop

**`255` is not reliably "ssh's own error".** OpenSSH documents 255 for its own failures and passes
the remote command's status through otherwise — but a wrapper in the remote command can produce it
too. Measured through `ssh → cmd.exe → wsl`:

```
ssh host "wsl -d NoSuchDistro -- true"   # → 255, indistinguishable from a dropped link
```

A changed host key and a revoked key are also 255. So "retry on 255" alone will loop forever on a
permanent fault. Gate it on something that distinguishes them — e.g. retry only once an attempt has
lasted long enough to prove a session really was up.

**`tmux attach` exit codes**, measured on tmux 3.4 (run on two throwaway `-L` sockets so nothing
live is at risk):

| Ended by | Exit |
|---|---|
| `detach-client` — the same `MSG_DETACH` that `Ctrl-b d` sends | **0** |
| the session killed under the attached client | **0** |
| `kill-server` | **1** |
| attaching to a session that does not exist | **1** |

So `0` means the person left or the work ended, and a loop must stop on it; the `1`s are worth
reporting and stopping on too.

## The remedy, and why no wake hook is needed

Two parts, and the first is what makes the second possible:

1. **`ServerAliveInterval` as a deadline, not a keepalive.** It sends nothing while the machine is
   asleep and cannot save the connection. What it buys is that the death becomes prompt and
   deterministic — `ServerAliveInterval=15 ServerAliveCountMax=4` is 75 seconds — instead of
   arriving at an arbitrary hour. Set it on the invocation rather than in `~/.ssh/config` when only
   one kind of session wants it: a 75-second teardown is right for a tab somebody is watching and
   wrong for every other ssh to that host.
2. **A retry loop in the tab**, replacing `exec ssh` with a loop, so the tab's own process survives
   the disconnect and runs the attach again.

**A wake trigger adds nothing.** `NSWorkspace.didWakeNotification` via a LaunchAgent is achievable,
but ssh's alive deadline is absolute against a clock that advances through the suspend, so the
overdue probe goes out on its first pass after resume. Anything a wake hook did would have to kill
the hung ssh to accomplish anything, which is what the keepalive already does — and the hook cannot
help at all with the other half of the problem, the far machine restarting while the laptop is
awake.

Two things to check before replacing `exec ssh` with a loop, both of which bit here:

- **Anything that identifies the tab by its foreground process changes meaning.** With `exec`, the
  tab's leader is `ssh`; with a loop it is the shell, for the tab's whole life. On macOS a terminal
  that names a pane by its process-group leader will report `/bin/sh <script> <args>` from then on,
  so a matcher looking for the ssh command line stops matching, and any classifier that reads a
  shell as "idle prompt" starts reading the tab as empty.
- **The title stops being maintained.** Whatever blanks or updates it usually runs on the far side
  and never gets to. Decide what the tab should say while disconnected, and make sure that string
  cannot be mistaken for a live status by anything that parses titles.
