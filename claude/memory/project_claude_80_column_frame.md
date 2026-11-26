---
name: project_claude_80_column_frame
description: Open bug since 2026-10-09 — a Claude pane on the Windows box draws at 80 columns inside a full-width tmux pane after a boot; the investigation lives in the agwinterm repo
metadata:
  type: project
---

When a Claude Code session on the Windows machine comes up drawing at 80 columns inside a much
wider pane (lines ending around column 80, fragments pasted beside them), that is a known open bug.
**Do not resize the pane first** — a resize clears the evidence. Note the tmux session name, read
WSL `~/tmux-size.log` for that session (logging hooks in WSL `~/.tmux.conf` write it), then resize.

The likely remedy is in place: `remote_session_create` in `claude/remote-session/lib.sh`, which
both `start-here.sh` and `cc-session.sh` call, sizes the new window to the attaching terminal with
`resize-window -x C -y R` and then `set-option -wu window-size` (e3b2a21, 2026-11-25). The earlier
`new-session -x/-y` (e721f9e) never sized the window while any client was attached to the server,
since tmux 3.4 then applies those flags only to the session's default size. Only a recurrence after
e3b2a21 weighs against the creation path. The full record — what was measured, what was ruled
out — is the agwinterm repo's project memory `claude-80-column-frame.md`; route the occurrence to
a live agwinterm session if one exists (the `peer` skill). agwinterm itself was measured not at
fault.

Delete this file and its index line once the cause is found.
