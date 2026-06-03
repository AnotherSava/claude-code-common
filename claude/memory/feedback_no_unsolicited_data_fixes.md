---
name: no-unsolicited-data-fixes
description: When a code fix changes behavior going forward but leaves old/stored data wrong, fix the code only — don't proactively migrate/correct past data unless asked or after asking
metadata:
  type: feedback
---

When a bug fix corrects behavior going forward but already-stored / historical data remains in the old (wrong) state, fix the code and stop. Do NOT proactively offer or perform one-time data migrations, cleanup scripts, or console snippets to correct the stale past data. If a past-data correction seems warranted, ask first (or wait for an explicit request).

**Why:** After fixing the BGA arena-classification probe, I unprompted offered a service-worker console snippet to overwrite the stale stored "arena" entry for one table. The user said: "don't bother with one-time fixes of the past data unless I request that explicitly; or at least ask beforehand." They find unsolicited past-data corrections noise.

**How to apply:** It's fine to *mention* that stale data exists (e.g. "the already-stored value won't auto-correct because of first-write-wins"). But stop there — no migration code, no correction snippet, no executing a fix — unless the user asks, or you've asked and they agreed. Default to fixing only the going-forward code path. Related: [[feedback_post_iteration_cleanup]] (clean up cruft from *this* session) is different — that's about my own working changes, not the user's historical data.
