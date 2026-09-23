# A Claude session on the Windows machine, open from both machines

Some work only the Windows machine can do — a WinForms tray app, a Tauri build, anything that has to
appear on a real desktop. Running Claude there over an ordinary SSH connection gets you a session
that dies the moment the laptop lid closes, and one that only the machine you opened it from can see.

This gives you a session that keeps working while you are away from it, and that you can watch from
agterm on the Mac and from a terminal on the Windows box **at the same time**. The agent is a native
Windows process with a `D:\...` working directory, native toolchains and desktop access; WSL and tmux
only hold the terminal it lives in.

## Using it

From the Mac, press **cmd+shift+r** in agterm. A fuzzy picker lists the Windows machine's attachable
sessions, each with its status and what it is working on; choosing one opens it as a tab in a
workspace called `remote`, created on first use. Picking a session that already has a tab selects
that tab rather than opening a second client on it.

To start something new, take the last row — **Start a project…** — which opens a second picker over
the projects on that machine, so a name is completed rather than remembered. It is a second step
rather than part of the first list because those folders would bury the handful of running sessions
the keystroke exists for.

A folder is offered when it holds a `.claude` directory, which Claude Code creates the first time it
runs somewhere — so the list is the places Claude is actually used rather than every folder on the
disk. On this tree that is 23 projects out of 153 folders; `.git` would have offered 29, mostly
adding third-party clones while missing two working folders that are not repositories. A project
Claude has never run in has no marker yet, and is reached by typing its path.

Attachable means running inside the holder's tmux server, which is what every session started
through `claude` on that machine now does. A Claude started some other way — an older session, or
one launched outside the shell function — owns its terminal's own pty, and nothing can join it, so
the picker leaves it out rather than offering something that cannot be done.

The status and task beside each row come from the Claude Code Dashboard. That is decoration: when
the dashboard is not running the rows still list, without it.

On the Windows machine, start a session the way you always did — `claude` in the project directory.
The shell function now runs it inside the holder's tmux server, so it survives a disconnect and the
Mac can attach to it later. Nothing about how you invoke it changed: it resumes the conversation
already in that directory and starts one where there is none. To set a running session back to a
fresh conversation, use `/clear` inside it, from whichever terminal is watching.

Claude Code's own subcommands — `claude update`, `claude doctor`, `claude mcp` and the others
`claude --help` lists — run straight through, outside tmux, because they open no session. So do the
flags that print and exit, and `--print`. Only an interactive session is wrapped, which is why the
one-per-directory rule below never stands in the way of updating.

One session per directory, and one terminal per machine onto it. Running `claude` where a session is
already going attaches to that session instead of starting a second conversation in the same
project — including while the Mac is watching it, which is the pair of viewers the whole design is
for. It refuses only when a terminal on this machine is already attached, which would be two windows
onto one pane. Two directories that share a last name — `scheduler/docs` and `travel/docs` — are different sessions, because the name is
built from the whole path below the projects root.

Which machine a client is at is recorded by whatever attached it, and read back off that client's
own process. Nothing infers it: measured against one local client and one from the Mac, every
ambient signal separated them for reasons that were not the machine, and `attach.cmd` runs on this
box the same script the Mac runs over ssh, so a second local terminal reproduces the remote's
fingerprint exactly. A client that recorded nothing is therefore refused rather than guessed at.

To re-attach a session already running there, from this repo's root:

```
claude\remote-session\windows\attach.cmd scheduler
```

Every route creates the session if it is not running yet and attaches to it if it is. Opening a
second client while the first is attached is the point, not a conflict. A route that has to create
one resumes the conversation already in that directory, whichever machine it is invoked from, so
picking a project from the Mac comes back to where that project was left rather than starting over.

Detach with tmux's `Ctrl-b d`. The session and everything in it keep running; closing the terminal
or dropping the connection does the same thing.

### The keystroke, and why it is not the attach command

The keymap line runs `mac/pick-session.sh`, not the attach directly. agterm runs a keymap command
via `/bin/sh -c` **detached with no terminal**, so a full-screen program bound straight to a chord
has no TTY and exits the moment it starts. The script instead asks agterm for a real session and
hands it the attach as that session's process, which is where the TTY comes from.

Rebind it by editing the `command "Remote session"` line in `~/.config/agterm/keymap.conf` and
running `agtermctl keymap reload`. That file is per-machine and is not part of this repo.

For a tab to come back attached after an agterm restart, turn on restoring running commands in
agterm's settings; the default brings it back as a plain shell. The `tmux` entry in
`restore-denylist.conf` does not apply here — it matches on basename, this is `attach.sh`, and
re-running it reattaches to a session that is genuinely still alive on the other machine.

### What the two terminals share

Both clients draw the same session, so both see every keystroke either of you types. tmux sizes a
shared pane to the **narrowest** attached client, so a 120-column agterm tab and a 200-column Windows
terminal both render at 120. Detaching the narrow one widens the other on its next redraw.

## Setting it up

Run the installer on the Windows machine, from this repo's root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File claude\remote-session\windows\install.ps1
```

**Re-run it from an Administrator PowerShell.** A first install needs no elevation; replacing a
registration that already exists does, because the task file grants the account that created it
read-only access — `icacls %SystemRoot%\System32\Tasks\ClaudeRemoteSessionHolder` shows who can
write it. A run without elevation stops at that point and says which task it could not replace,
leaving the holder as it found it.

It writes `%USERPROFILE%\.wslconfig`, registers a hidden scheduled task called
`ClaudeRemoteSessionHolder`, starts it, and then checks that the holder came up rather than assuming
it. Re-run it after changing anything under this directory — in particular `holder.sh` and
`run-hidden.py`, which run from copies outside the checkout and are refreshed only by the installer.
They live outside it because a running script is an open file handle on Windows, and leaving either
in place makes `git pull` on that machine fail while the holder is up.

It also writes the `claude` function into every shell that has a profile. Git Bash, Windows
PowerShell 5.1 and PowerShell 7 each read their own file and none of them is version-controlled, so
it builds the function from `config.secret.env` rather than leaving them to be kept in step by
hand. It leaves a function that already calls `start-here.sh` alone, and prints the replacement for
one that does anything else rather than overwriting it, since a profile holds plenty the installer
did not write.

After the repo moves or the distro is renamed, that is the only part that has to run again — it
touches neither the holder nor the scheduled task, so nothing running dies:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File claude\remote-session\windows\install-shells.ps1
```

**Close your sessions before re-running it.** Re-registering the task stops the holder, and every
session's `claude.exe` belongs to that holder's job object, so all of them are killed — the tmux
server itself survives, which makes the loss easy to miss until you look for a session that is no
longer there.

The Mac needs nothing installed. It needs SSH access to the Windows machine, which
`claude/learnings/windows-openssh-over-tailscale.md` covers.

Both halves come from one checkout of this repo, present on both machines, so a single `git pull`
delivers the Windows scripts and the Mac script together.

### Machine coordinates

Host alias, account, distro name, projects root, the path to `claude.exe`, and the name the
dashboard knows that machine by all live in `config.secret.env` beside this file, encrypted in git
with transcrypt and plaintext in your working tree. The dashboard's device name is its own key
rather than a reuse of the ssh alias: they are separate facts that only happen to resemble each
other, and the roster is matched on it exactly.

A fresh clone reads the file as ciphertext until transcrypt is unlocked there once, which the
`/transcrypt` skill does. Every script checks for that state by name, so an unlocked-clone failure
says so instead of surfacing as a missing setting.

## When something is wrong

**Attaching says the holder is not running.** The scheduled task stopped, most often because you
logged off and back on without it re-triggering. Start it:

```powershell
schtasks /run /tn ClaudeRemoteSessionHolder
```

**Attaching says `no server running`.** Same cause, one layer down — the tmux server belongs to the
holder. Starting the task brings it back. Sessions that were running are gone; they do not survive
the holder.

**The session vanished after a disconnect.** A session is only durable if the holder's tmux server
created it. `attach.sh` and `attach.cmd` both refuse to start one any other way, so this means
something started `tmux new-session` directly over SSH — use the scripts.

**A session you started with `claude` is not in the picker.** That shell's `claude` function is
launching `claude.exe` itself instead of going through `start-here.sh`, so the session owns its
terminal's own pty and nothing can attach to it. Run the shell installer above, which names the
profile and prints what to put there, then restart that terminal — a shell reads its profile only at
startup, so the window you are standing in keeps the old function however the file now reads.

**It says a client is attached that recorded no machine.** That client attached before the origin
was recorded, or by driving tmux directly. Reattach it — cmd+shift+r on the Mac, `attach.cmd` here —
and `claude` can tell it from a terminal on this machine again. Every client attached at the moment
this shipped reads that way once, and clears on its next attach.

**A subcommand answers with "attach to the session already running here".** Claude Code has gained a
command that the pass-through list in `wsl/start-here.sh` does not name, so it was treated as a
request to start a session. Add it to that list — `claude --help` prints the current set.

**A folder with a space in its name is refused from the Mac.** The project name is data travelling
through the Windows shell, where `a b` arrives as `a` and no quoting prevents it — so it is refused
at the boundary rather than opening on the wrong directory. Start that one on the Windows machine
with `claude` in the folder, which passes nothing across.

**Nothing explains it.** The holder writes to
`%LOCALAPPDATA%\claude-remote-session\holder.log`. It is the only place a failure can surface,
because the launcher runs under `pythonw` to keep a console window off the desktop, and `pythonw`
discards everything else.

## What it does not survive

Logging off ends the holder, and with it every session. The task is triggered at logon, so logging
back on restores the holder — but the sessions themselves are gone and must be started again. A
reboot is the same thing with extra steps.

This is the cost of running in the interactive desktop session, and it buys the thing the setup
exists for: a background service session cannot reach the desktop, so an agent hosted there could
build and test a Windows GUI app but never see it or drive it.

## How it is put together

Every piece below exists because something simpler was measured not to work; the measurements are in
`claude/learnings/windows-persistent-terminal-session.md`.

- **`.wslconfig`** stops WSL shutting an idle distro down, which it otherwise does about 45 s after
  the last connection closes.
- **`wsl/holder.sh`**, run by the scheduled task, holds the distro open and owns the tmux server.
  Both matter: a tmux server created over SSH hands every Windows process inside it to that
  connection's job object, so its sessions die at disconnect while everything around them stays
  healthy.
- **`windows/run-hidden.py`** launches the holder with no console window, and logs what it otherwise
  could not report.
- **`wsl/cc-session.sh`** creates or attaches one project's session, running the native `claude.exe`
  from a `/mnt/d` working directory so the Windows child gets a real `D:\...` path.
- **`wsl/start-here.sh`** is what the Windows machine's `claude` function runs. It does the same for
  whatever directory you are standing in, which is what makes every session started there
  attachable. Every shell on that machine calls it and nothing else, so no profile carries behaviour
  of its own that can drift from the rest.
- **`windows/install-shells.ps1`** puts that call in each shell's profile. It builds the call from
  the config, so a repo that moves or a distro that is renamed rewrites every profile from one
  place.
- **`mac/attach.sh`** and **`windows/attach.cmd`** are the two ways in, and
  **`mac/pick-session.sh`** is what the keystroke runs: it asks tmux on the far side which sessions
  exist, decorates them from the dashboard, opens agterm's picker, and creates the tab in the
  `remote` workspace.
- **`lib.sh`** holds what more than one piece has to agree on: the config loader, the rule for naming
  a session, the keepalive session's name, the check for whether the holder is up, the read that
  turns a session's attached clients into the machines they are sitting at, and the option that
  keeps a pane whose command failed — without it a session created for an argument Claude Code
  rejects disappears in the same instant, taking the error with it. The next `claude` in that
  directory prints what the pane said, clears it, and starts a fresh session. Each is there
  because the alternative is two copies drifting — two scripts deriving a name from different inputs
  and disagreeing about it, or a rename that leaves three other places looking for a session nobody
  creates. The installer reads the keepalive name out of this file rather than repeating it, since
  PowerShell cannot source it.

tmux rather than `claude --bg` and `claude attach` is the one design choice worth knowing about:
`claude attach` serves a single viewer, and a second attach takes the session away from the first.
Everything above is the price of the second viewer. If you ever stop wanting it, that pair needs no
WSL, no tmux and no scheduled task.
