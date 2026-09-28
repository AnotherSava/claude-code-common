---
name: feedback_realism_before_hardening
description: Before building for an edge case a review found, rate how realistic it is; a rare scenario that is harmless or cheap to handle by hand is reported with its rating and gets at most a warning or a doc sentence — not code
metadata:
  type: feedback
---

**Before building for an edge case a review found, rate its realism.** Who hits it — a known
writer, a user report, a documented path? What does it cost when unhandled? A scenario that is rare
**and** harmless or cheap for the user to handle by hand is still reported, with its rating, and
gets at most a log warning or a sentence in the docs, never code. Code is for data loss, crashes,
lost or duplicated core output, and leaks of the user's own identity.

**Why:** seen 2026-09-26/27 in achievement-overlay. Eight fix-and-review rounds each ended with a
fresh "found and not fixed" list, the user said "y" to each next round, and the fixes added about
2,500 lines of source and tests: a watcher retarget for a sub-second window, millisecond timestamps
no emulator writes, network-share paths, junction detection. The user judged two scenarios
impractical. On a game with folders in two GSE Saves paths, whose redesign had been parked, they
said "it feels like not a practical scenario — should we just add a warning", and the warning that
replaced it gained junction detection. On games installed on a network share they said "if 1 out of
1000 users does this, and it happens that they need to file a report, and it happens that they want
to hide that particular game — they will just remove it by hand". Then they asked "are there any
other weird use cases you've build logic around?". An audit against that standard removed about a
thousand of those lines again.

**How to apply:**
- Every "found and not fixed" list carries a realism rating per item (common / plausible / rare /
  theoretical) and what goes wrong if it stays unhandled. Present it as a triage, not a to-do list.
- Don't offer "run another round" by default when what is left is rare; say the rest is edge cases,
  and name the ones worth code.
- A reviewer confirming that the code mishandles a scenario is not evidence that anyone will be in
  it. Ask for the writer or the report before building.
- This narrows [[feedback_loud_errors]] beside its self-healing exception: a rare case that is cheap
  to handle by hand gets a log line and a docs sentence without the in-UI error row. Loud surfacing
  still applies to a failure the user cannot notice and act on, and a case whose unhandled path
  would silently lose or corrupt core output is not harmless — it belongs in the code list above.

**When review rounds stop shrinking, triage against practice before fixing.** On 2026-09-28 four
adversarial rounds over the docs-relevance skill confirmed 9, 23, 21 and then 31 findings: each round
reviewed code the previous fixes had added, so the count never converged. Checking each finding with
the session that actually ran the tools, and against its transcript, sorted the 31 into real ones a
committed frame or a real caller hits, cheap ones, and theoretical ones no caller reaches — one of
whose proposed repairs would have broken a committed capture step. So after a second round that does
not shrink, classify every finding as fix / theoretical / wrong against real callers, committed
artifacts and the owning session's own record; fix the real ones, and memo the theoretical ones with
their evidence instead of hardening against them.

Related: [[feedback_complexity_may_be_self_imposed]], [[feedback_no_defensive_fallbacks]],
[[feedback_check_the_limit_is_real]], [[feedback_loud_errors]].
