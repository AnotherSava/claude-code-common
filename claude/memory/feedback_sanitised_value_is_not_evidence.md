---
name: feedback_sanitised_value_is_not_evidence
description: Clamping or defaulting a value for one consumer destroys the evidence a downstream guard reads from that same variable
metadata:
  type: feedback
---

When a value is coerced into a safe range — `max(x, 0)`, `or 0`, `?? default`, a swallowed exception — ask who **else** reads it. A consumer that needs the value to keep working is well served by the coercion. A guard that reads the same variable as *evidence that something went wrong* is blinded by it, and says nothing.

**Why:** on 2026-08-28, a Caddyfile linter clamped its brace-depth counter with `max(depth + delta, 0)`. That was correct for its main consumer: without it, one stray `}` would drive the depth negative and switch off every rule guarded by `depth == 0` for the rest of the file. But the same variable was also returned as the file's final depth, where a guard refused any file whose depth had not come back to zero — with the message "a clean result would be meaningless". An over-closed file therefore ended at a clamped zero and printed `clean — satisfies R1-R7`, while its under-closed twin was correctly refused. Thirty-two tests passed, because every balance case tested the direction that already worked. The fix was two values: keep the clamped one for the rules, return the unclamped one as evidence, plus a flag for the case where imbalances cancel.

**How to apply:** the tell is a guard whose error message describes a condition the guard cannot actually detect — read those messages as claims and check each one. When a single variable serves both a working consumer and a detector, give the detector its own. And when a guard exists to catch "I lost track", test it in every direction of losing track, not just the direction that was easy to write; a suite that covers one side of a symmetric guard reads exactly like a suite that covers both. Related: [[feedback_guard_the_input_not_the_output]] and [[feedback_not_run_is_not_pass]].
