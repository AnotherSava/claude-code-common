---
name: feedback_clear_provably_stale_blockers
description: When state that blocks an operation can be shown to be stale, clear it inside the operation instead of refusing with retry advice or waiting for a background sweeper
metadata:
  type: feedback
---

When an operation is blocked by state you can positively show is stale, have the operation clear it itself rather than refusing with "retry in a few seconds" or waiting for whatever background process normally cleans it up. Keep the refusal only for the case the evidence cannot settle.

**Why:** a project-rename route in the dashboard refused while the renamed project's row was still present, and the proposed fix was to wait out the liveness reaper. The user asked "why not just remove the row?". The row's session was provably over: Claude Code's live-session list did not name it and its recorded process was dead. Removing it there also saved its dialog, which the rename then carried over. Waiting would have cost every user a retry, and a row whose process was never recorded would never have cleared at all.

**How to apply:** before designing a wait, a retry loop or a "try again" message around something in the way, ask what evidence would prove it stale, and whether the operation can check that evidence and clear the obstacle through the same path that normally removes it. Refuse only where that evidence is missing or unreadable, which is the direction that cannot destroy live work. See [[feedback_check_the_limit_is_real]].
