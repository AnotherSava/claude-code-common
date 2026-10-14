---
created: 2026-10-13 22:59:57
---

# Confirm a Mac remote tab recreates its session after the Windows machine reboots

Since 3df2807 (2026-10-13), mac/attach.sh runs cc-session.sh in create mode on every attempt, so a tab whose session is gone should start it again, resuming that directory's conversation, with no prompt. Nothing has observed it yet. Killing the tmux session while a tab is attached does NOT test it: tmux exits the client with 0 and attach.sh's case 0 stops the tab by design. The path only runs when the transport drops AND the session is gone, which is what a Windows reboot does. Test: leave a remote tab open on the Mac, reboot the Windows machine, and wait for the tab's reconnect (up to five minutes of backoff). Expect the tab to come back attached to a fresh claude.exe that resumed the conversation, not stopped on 'not connected' or 'refused'. Without a reboot: on Windows, kill the tmux server holding the cc-* sessions while the Mac's ssh is cut (e.g. sleep the Mac first), then wake it. If the tab exits 1 instead, cc-session.sh's attach-after-create raced or failed; read the lines above the attach message.
