---
name: feedback_comparison_you_supply_both_sides
description: a predicate whose two sides you both control has stopped comparing; relocate a term you remove, never just drop it
metadata:
  type: feedback
---

A verdict of the form `stamp >= watermark` is a recency test. Stamping the watermark itself makes it a tautology — the comparison is still there to read and no longer tests anything.

**Why:** the dashboard marks a finished row read when `attended_at >= content_at()`, which is what makes a stale observation leave the row unread. Extending that to a session synced from another machine, I could not use this machine's clock on the far machine's timestamps, so I stamped `content_at()` — a value the origin minted. That solved the clock problem and silently made the predicate unconditionally true, so any observation credited the row however old. Stale ones turned out to be routine rather than exotic: the terminal mints an input instant as `now - idle` from the desktop-wide idle clock, so one keystroke and then walking away re-offered the same frozen instant every tick, 132 times in the log at a median age of 186 s and a maximum of 594. The local path had been correct the whole time precisely because its two sides came from different places. Two review agents found it independently; I had read the same function and not seen it.

**How to apply:** when both sides of a comparison come from the same source, it is not a comparison. Removing a term because it is in the wrong units means **relocating** the test, not deleting it — here, recording when the content *arrived on this machine* put both sides back on one clock and kept the stamped value the origin's. Ask of any `a >= b` you write or review: can I name a reachable state where this is false? If not, either the check is dead or the thing it was guarding is now unguarded, and the second is the expensive one because the code still reads as careful.

Related: [[feedback_fixture_must_exceed_the_cap]], which is the same vacuousness one level down — a test fixture that never reaches the branch it names; and [[feedback_not_run_is_not_pass]], where a check that cannot distinguish success from never-having-run reports the wrong one.
