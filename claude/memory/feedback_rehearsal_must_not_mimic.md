---
name: feedback_rehearsal_must_not_mimic
description: A test or rehearsal must never be indistinguishable from the real signal in the part read first — subject lines, notifications, alerts
metadata:
  type: feedback
---

A test or rehearsal must never be indistinguishable from the real signal **in the part that gets read
first**. Building an alerting path, I sent a test with the subject
`[landlord] selfcheck FAILED on netcup — test of the alert path`. The body said it was a test; the subject
asserted a failure that had not happened. The subject is what shows in a notification, on a lock screen, in
an inbox list — and it is often the only part read.

**Why:** this is a reliability problem, not a manners one. A reader who learns that `FAILED` sometimes means
nothing is exactly the reader who ignores the real one at 3am. It degrades the channel permanently and
silently, and no test will ever catch it — the channel keeps working perfectly while becoming worthless.
It is the same defect as a check that reports success for something it did not check, pointed at the
notification instead of at the check.

**How to apply:** decide what a rehearsal looks like *before* sending the first one — the first is always
sent while nobody is thinking about wording, and by then the convention is whatever was typed. The word
naming the real state must not appear in a rehearsal at all; give each state its own shape (failure,
recovery, stale, test) and make the test say plainly that nothing is wrong. The rule does not stop at
wording: a rehearsal must not consume the real thing's rate limit or reset its clock either, because a
rehearsal that silences the real alert is the same defect one layer down.

Related: [[feedback_no_guessed_facts]], [[feedback_microcopy_user_facing_state]].
