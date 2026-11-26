---
created: 2026-11-25 23:21:13
---

# Keep a /yolo push in a repo with no review bookmark inside the next review

Found by the review-auto run in the dotfiles /wrap-up, 2026-11-25. With no refs/review/last, review_scope.py takes a review's base from where HEAD forks from its upstream (claude/scripts/review_scope.py _coverage). A /yolo push moves that upstream to HEAD, so the commits it pushed fall out of the next review's scope and are never reviewed. The forecast line printed before the push now says so (_coverage_part with pushing=True), but nothing keeps them in scope. Options to weigh: have shared/push.py record a bookmark at the pre-push upstream when none exists, or have the first /wrap-up in a repo with no bookmark start from the oldest commit not reviewed by any run. Either changes what a bookmark promises, so decide before building. Next step: reproduce in a scratch repo (upstream set, no bookmark, two commits, push.py, then review_scope.py scope) and pick the option.
