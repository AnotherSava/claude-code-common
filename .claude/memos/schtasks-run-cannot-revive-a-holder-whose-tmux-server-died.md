---
created: 2026-09-24 21:04:24
platform: windows
---

# schtasks /run cannot revive a holder whose tmux server died while holder.sh still runs

claude/remote-session/wsl/holder.sh creates the _holder keepalive session once (remote_session_holder_up || tmux new-session ...) and then runs 'sleep infinity'. If the tmux server dies while holder.sh is still alive (tmux kill-server, a crash), the scheduled task stays Running, and install.ps1 registers it with -MultipleInstances IgnoreNew, so 'schtasks /run /tn ClaudeRemoteSessionHolder' is silently ignored. That is the remedy the README's 'Attaching says the holder is not running' entry gives, and the error text in wsl/cc-session.sh and wsl/start-here.sh says the same.

Two ways to close it, a choice to make first:
- Documentation only: tell the reader to check 'schtasks /query /tn ClaudeRemoteSessionHolder' and run 'schtasks /end' before '/run' when it still shows Running; update the README entry and both scripts' error text together.
- Make holder.sh loop: re-check remote_session_holder_up periodically and recreate the keepalive session, so a dead server comes back without anyone acting. This changes holder.sh, which runs from a copy only install.ps1 refreshes, and re-running install.ps1 kills every running session, so schedule it for a moment with no sessions open.

Found 2026-09-24 by the verification pass over the remote-session doc fixes (commit 88290a3); it predates that change. Needs the Windows machine: the holder, the task and WSL tmux only exist there.
