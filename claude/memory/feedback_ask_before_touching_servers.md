---
name: feedback_ask_before_touching_servers
description: Don't silently start or (especially) stop local dev servers — the user may have their own running; announce starts, ask before stops
metadata:
  type: feedback
---

When verification needs a running app, don't silently start a dev server and later kill it. The user may already have their own server on that port, and killing "the" process on `:3000` stops their work.

**Why:** During a session I started `npm run dev` for a visual check, then later killed the process on port 3000 (plus a debug-Chrome instance) without announcing any of it. The user asked "did you kill a local server?" — they'd lost their running server.

**How to apply:** Announce when you start a server for verification. Before stopping any server or long-running process you didn't clearly start *this turn*, ask first. After verifying, offer to stop the one you started rather than assuming. Prefer a separate port / dedicated debug profile to avoid colliding with the user's instance. Relates to [[feedback_user_run_commands_bang_prefix]] (run verification yourself) but adds: long-running/shared resources are the exception — touch them transparently.
