---
name: feedback_remeasure_before_concluding
description: A status other live sessions are changing goes stale in minutes; re-measure right before reporting a conclusion, never reuse a reading from earlier in the session
metadata:
  type: feedback
---

When other agents are working on the same thing — a key rotation across repos, a fleet-wide migration, a
shared deploy — a status reading is a snapshot of a value that is actively moving. Re-measure at the moment
of **concluding**, and report the measurement with the commit or time it was taken at. Never restate a
reading from earlier in the session as the current state.

Seen 2026-09-29 during a transcrypt passphrase rotation: two sessions on different machines each reported
repos as still under the old key. Both readings were correct when taken, and three of the four repos were
rekeyed by sibling sessions within minutes, so both reports were false by the time anyone acted on them. The
report that held up re-fetched and re-decrypted every blob immediately before concluding.

**How to apply:** before a "still broken" or "done" verdict about shared state, re-run the measurement in
the same turn that states the verdict, and name the ref it was taken against (`origin/main @ <sha>`). A
reading from an earlier turn is evidence of where to look, not of what is true now. Related:
[[feedback_live_values_source_of_truth]], [[feedback_sample_level_miss_edge]].
