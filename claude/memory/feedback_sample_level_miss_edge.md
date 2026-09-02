---
name: feedback_sample_level_miss_edge
description: Polling a level can't detect a transient edge; shortening the interval narrows the blind window and never closes it
metadata:
  type: feedback
---

**Polling a level cannot detect a transient edge.** When the requirement is "did the user *do* X", sampling "is the system *in* state X" misses every X shorter than the poll interval — and shortening the interval narrows the blind window without ever closing it.

Real case (tauri-dashboard, 2026-09-02): "has the user opened this finished session's tab" was detected by polling which tab was selected and diffing against the previous poll. A tab opened and left between two samples was invisible — the sampler saw the tab before and the tab after and never the one in between. The user hit it within an hour of shipping. A 30s back-off for long-unread rows made it worse, added on the reasoning that "the answer stops changing quickly" — true of a *state*, false of an *event*, which can happen at any instant.

**Why:** the failure is silent and dressed as a tuning problem. Every individual miss is plausible as "the sensor just needs to run more often", so the structural defect hides behind a knob that appears to be helping.

**How to apply:**
- Before building a detector, say plainly what it *samples* versus what was *asked for*. If those differ, the gap is permanent — no interval closes it.
- Prefer an edge from the source: an event carrying a timestamp. Check whether the source already offers one before settling for a poll. In the case above it had been *offered* and declined, on reasoning that contradicted documentation already read (the events carried the timestamp I claimed they lacked).
- When no edge is available, state the limit in the code doc and the project map rather than tuning toward it, and make the miss fail in the recoverable direction (leave the thing showing, not hidden).
- A back-off is about how fast an *answer* changes. Never apply one to a detector watching for an *event*.

Related: [[feedback_not_run_is_not_pass]], [[feedback_check_the_limit_is_real]].
