---
created: 2026-11-08 09:55:59
---

# Decide how the review bookmark advances past a held-out untracked file, which makes change_scope.py re-run polished passes

Reported by the url-cleaner session 2026-11-08, seen three times. review-auto recorded and polished trees 11f4cf3, e4fd84b and 459d5a9 in url-cleaner, but a deliberately held-back untracked config/deploy.env (the pending convention-017 file) meant no commit could end at the reviewed tree, so review_scope.py advance reported 'not advanced'. claude/skills/shared/change_scope.py then printed RUN for clean-code and docs-relevance ('N code file(s) changed') instead of 'SKIP (review-auto polished this tree)', so /wrap-up re-ran passes the review had already run over the identical tree. The first run, before anything was committed, correctly gave SKIP. Suspected: the SKIP test compares against HEAD or the bookmark rather than the recorded polished tree's content. Next step: read change_scope.py's SKIP condition, reproduce with a scratch repo (record a polished tree, commit part of it, leave one untracked file), make SKIP key on the current tree matching the recorded polished tree (or the committed part plus the held paths), add a test.

## Diagnosis, 2026-11-08 (Windows session)

The suspected comparison is not the cause. url-cleaner has no `refs/review/last` at all, locally or on origin, and holds 5 unpushed commits from its held wrap-ups. A review launched with no bookmark scopes from HEAD, so from the second run on its `base` sits on top of commits not on any remote; `review_scope.polished_since` (claude/scripts/review_scope.py) then finds `rev-list <base> --not --remotes` non-empty and returns None by design, since its docstring says such a record "covers only part of what /wrap-up is about to send". Those commits were in fact reviewed and polished by the earlier run, but nothing records it, because `advance` could not move the bookmark while the held untracked file keeps every commit's tree from equalling the reviewed tree.

So the fix is in how the bookmark advances, not in change_scope: let `advance` move to the last commit whose tree equals the reviewed tree minus paths deliberately held out (and say which), or keep several bookmarks as the open "review bookmark becomes a list" memo proposes. Either changes what a recorded bookmark promises, which is the user's call; that memo and this one should be settled together.
