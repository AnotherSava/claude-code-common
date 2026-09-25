---
created: 2026-09-23 12:00:41
---

# Make Mac sessions attachable from a Windows terminal, the mirror of the Windows remote-session

Today nothing on the Mac can be joined: tmux is not installed there and no tmux server runs, so every Claude owns its agterm pane's own pty. That is the state the Windows box was in before claude/remote-session was built.

The build is far smaller than the Windows one, because every heavy piece there exists to defeat Win32-OpenSSH's job object killing whatever an SSH connection started — the holder, the scheduled task, the WSL keepalive, .wslconfig. macOS has no equivalent, so a tmux server started over SSH is expected to survive the connection dropping with nothing holding it open. That expectation is reasoned, not measured; it is listed under 'Still unmeasured' in claude/learnings/windows-persistent-terminal-session.md and should be the first thing tested.

Three pieces:

1. `brew install tmux` on the Mac.
2. A Mac equivalent of wsl/start-here.sh, called from the `claude` shell function already defined in ~/.zshrc — the same hook point the Windows shells use, so every session started there becomes attachable without changing how it is invoked.
3. A windows/attach-mac.cmd: ssh into the Mac and run that script for a named project, the mirror of mac/attach.sh.

What carries over unchanged: lib.sh's session naming, config loader and quoting, and the REMOTE_SESSION_ORIGIN convention — the new entry points pass `mac` and `windows` the same way the existing two do. Three other lib.sh pieces assume the Windows box hosts the session, so each needs a form that knows which machine is the host:
- remote_session_attach treats `windows` as the local origin. Used as is, it would badge the Mac's own tab with `⇄` and leave the Windows one unbadged; it has to compare the origin with the host machine instead.
- remote_session_resume_command builds in the WSLENV export and the title switch-off the Windows dashboard needs.
- remote_session_client_origins reads /proc/<pid>/environ, which macOS does not have, so every client would read as `unknown` and the one-terminal-per-machine refusal would fire whenever anyone is attached.

Transport is already in place and verified 2026-09-23: the Windows box's key is authorized on the Mac and an ssh whoami from there returns the Mac account's own name. Take the account and host from the machines-private memory. config.secret.env will need the Mac's coordinates added beside the Windows ones.

Note the Mac has no agterm picker equivalent on the Windows side — cmd+shift+r is an agterm keymap entry and agterm is macOS-only, so the Windows entry point is the attach script run by hand in Windows Terminal, not a picker.
