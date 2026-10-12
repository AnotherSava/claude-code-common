---
name: no-unsolicited-data-fixes
description: When a code fix changes behavior going forward but leaves old/stored data wrong, fix the code only — don't proactively migrate/correct past data unless asked or after asking, and don't judge a new feature by records made before it existed
metadata:
  type: feedback
---

When a bug fix corrects behavior going forward but already-stored / historical data remains in the old (wrong) state, fix the code and stop. Do NOT proactively offer or perform one-time data migrations, cleanup scripts, or console snippets to correct the stale past data. If a past-data correction seems warranted, ask first (or wait for an explicit request).

**Why:** After fixing the BGA arena-classification probe, I unprompted offered a service-worker console snippet to overwrite the stale stored "arena" entry for one table. The user said: "don't bother with one-time fixes of the past data unless I request that explicitly; or at least ask beforehand." They find unsolicited past-data corrections noise.

**Judging is the same trap as fixing.** A feature that acts only on future or live data is not measured against records collected before it existed. On 2026-10-11 a trip-coverage marker that shows only on unfinished trips was reported as "30 chain breaks across 108 trips", and four exchanges went into geocoders, lookup tables and record repairs to improve a number no screen would ever show — the user said twice that the old data "didn't expect that feature and didn't contain enough details and accuracy". Measure the feature where it acts, and where legacy records are the only sample available, say that is what they are.

**How to apply:** It's fine to *mention* that stale data exists (e.g. "the already-stored value won't auto-correct because of first-write-wins"). But stop there — no migration code, no correction snippet, no executing a fix — unless the user asks, or you've asked and they agreed. Default to fixing only the going-forward code path. Related: [[feedback_post_iteration_cleanup]] (clean up cruft from *this* session) is different — that's about my own working changes, not the user's historical data.
