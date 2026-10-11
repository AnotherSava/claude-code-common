---
name: feedback_keep_instrumentation_while_open
description: Diagnostic instrumentation for an unresolved bug stays until the cause is found; clean runs are not a reason to offer removing it
metadata:
  type: feedback
---

Diagnostic instrumentation for an unresolved bug (logging hooks, probes, extra log lines) stays
until the cause is found. Clean runs mean the trigger did not occur, not that the bug is gone, so
never offer removal as an equal option; recommend keeping it, and name it in memory so a later
session knows it is there and what to read when the bug recurs.

**Why:** On 2026-10-10, after two clean reboots, tmux size-logging hooks set up to catch an
intermittent bug were offered for deletion alongside keeping them. The user chose deletion, then
asked why removal had been offered while the bug was unfixed, and the hooks had to be reinstalled.

**How to apply:** When an instrumented bug fails to recur, report that it did not recur and that
the instrumentation stays. Offer removal only once the cause is identified or the user raises it.
Related: [[feedback_not_run_is_not_pass]].
