---
name: remote-tabs-always-recreate
description: Remote-session tabs always (re)create their session with no confirmation, decided 2026-10-13; attach-only reconnects, an Enter prompt and picker-side creation were rejected
metadata:
  type: project
---

A remote-session tab on the Mac always creates its session when the Windows machine no longer holds one, with no confirmation — on a pick, a reconnect and an agterm restore alike. Decided by the user on 2026-10-13, after a Windows reboot left every open tab stopped on "session ended".

Rejected the same day, in this order, so none of them needs proposing again:

- Reconnects that attach but never create, stopping with "close this tab, then cmd+shift+r".
- A "Press Enter to start it again, or cmd+w" prompt in that tab.
- The rule "a tab never starts a session on its own", with `mac/attach.sh` attach-only on every pass and `pick-session.py` creating the session over ssh before opening the tab. It came from the agterm session after an agterm restore silently recreated sessions; the user overruled it in favour of always recreating.

`wsl/cc-session.sh` lost its `reattach` mode and exit 3 with this, since `attach.sh` was the only caller.
