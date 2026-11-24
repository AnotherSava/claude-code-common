---
created: 2026-11-24 16:15:15
---

# Let review_scope.py push publish a bookmark a rebase moved off origin's

After a fork rebase, refs/review/last is re-pointed at the upstream ref, and push in claude/scripts/review_scope.py then refuses with "origin's bookmark ... is not an ancestor of the local one". The upstream-sync skill (step 6, item 2) works around it with a manual git push --force-with-lease on refs/review/last. Decide whether push should take that case itself, for example a force-with-lease against the fetched origin bookmark when the local one was deliberately reset, so the skill can drop the manual step. Measured by the agterm session on 2026-11-24.
