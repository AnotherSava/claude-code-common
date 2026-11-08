---
created: 2026-11-08 10:18:43
---

# Decide how review-auto's polish revert survives the auto-mode classifier

Reported by the landlord session 2026-11-08 (run wf_d1bc80ab-93f). The polish review found a doc gap, so the review-auto workflow ran 'python ~/.claude/scripts/review_scope.py revert --repo <landlord> --tree 6f415a41... README.md bin/host-publish'; the auto-mode classifier refused it without explanation (likely because both files had uncommitted changes), and the run ended 'bookmark: not recorded: the polish revert did not restore the reviewed tree', so that wrap-up committed under hold with no bookmark. Options landlord listed: (1) an allow rule for review_scope.py revert in settings — a permission change, so the user's call; (2) a revert path the classifier reads as non-destructive (e.g. restore from the recorded tree object into the worktree via a script whose name and args say so); (3) record the bookmark at the polished tree when every polish-review finding is drop, so no revert is needed. The decision for the user is which; (3) also changes what a recorded bookmark promises.
