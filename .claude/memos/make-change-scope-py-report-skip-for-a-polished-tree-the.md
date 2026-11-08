---
created: 2026-11-08 09:55:59
---

# Make change_scope.py report SKIP for a polished tree the bookmark could not advance to

Reported by the url-cleaner session 2026-11-08, seen three times. review-auto recorded and polished trees 11f4cf3, e4fd84b and 459d5a9 in url-cleaner, but a deliberately held-back untracked config/deploy.env (the pending convention-017 file) meant no commit could end at the reviewed tree, so review_scope.py advance reported 'not advanced'. claude/skills/shared/change_scope.py then printed RUN for clean-code and docs-relevance ('N code file(s) changed') instead of 'SKIP (review-auto polished this tree)', so /wrap-up re-ran passes the review had already run over the identical tree. The first run, before anything was committed, correctly gave SKIP. Suspected: the SKIP test compares against HEAD or the bookmark rather than the recorded polished tree's content. Next step: read change_scope.py's SKIP condition, reproduce with a scratch repo (record a polished tree, commit part of it, leave one untracked file), make SKIP key on the current tree matching the recorded polished tree (or the committed part plus the held paths), add a test.
