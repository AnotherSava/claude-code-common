---
name: sync_watermark_matches_append_order
description: Gate replication on an append sequence, not an event timestamp, unless one sequential writer guarantees monotonic timestamps
metadata:
  type: feedback
---

When syncing an append-only log between devices, the "what have I not seen yet" watermark must be monotonic **in the dimension you gate on**. An event timestamp only qualifies when a single sequential writer produces the records; anything that appends from several sources, re-appends a revision, or back-fills history will emit timestamps that go backwards, and a `ts > held_max` filter then discards those records **silently** — no branch, no counter, no log. Use a per-device append sequence instead, and keep the event time as data.

**Why:** on 2026-08-28 I was adding a second synced store beside an existing one that gated on `ts > held_max`. Copying that rule looked obviously right — same shape, same transport, same code two files over. It would have been wrong: the new records are appended by a tree scanner (concurrent sources, out of order), by revision (an older timestamp re-appended), and by a one-time import writing weeks below the current maximum. Each case would have been dropped at three independent points, and the loss would have been invisible because a missing data point looked exactly like a genuine zero.

**How to apply:**
- Ask what *writes* the log before reusing a neighbour's watermark. "One poller on a timer" and "a scanner over many files" need different rules even when the wire format is identical.
- Start sequences at 1 so 0 is an unambiguous "I hold nothing" — with a 0-based sequence, a peer asking for everything never receives the first record.
- Prefer a merge that is idempotent on content (dedupe by a stable id) so the watermark is an optimisation rather than the thing correctness rests on.
- Watch for the general shape: silent discard is the dangerous failure, because absence is indistinguishable from a legitimate empty value. Related: [[guard_input_must_survive_the_event]], [[feedback_not_run_is_not_pass]].
