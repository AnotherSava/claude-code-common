---
name: Pre-push hook rejects unsigned + Claude-attributed commits
description: User's git push hook rejects commits that are not GPG-signed OR carry Co-Authored-By trailers mentioning Claude/anthropic
type: reference
---

User's pre-push hook rejects a push if ANY commit in the pushed range fails either check:
- Not GPG-signed (`%G?` is not `G`)
- Carries `Co-Authored-By:` trailer matching `Claude` or `anthropic`

The hook reports each failing commit hash and the specific reason, then exits non-zero.

## Own commits

Always use `git commit -S` (enforced by the shared `commit-message-rules.md` skill). Never bypass the hook with `--no-verify` without explicit user permission.

## First push to a new remote with inherited history

If the repo was cloned from another project, ancestor commits are almost certainly unsigned and may carry Claude trailers. Before the first push:

Re-sign ancestor history (preserves original Author, updates Committer, adds GPG signature):
```
git rebase --exec "git commit --amend --no-edit -S" --root
```

If ancestors also have Claude Co-Authored-By trailers, strip them while signing in one pass:
```
git rebase --exec 'git log -1 --format=%B | sed "/^Co-Authored-By:.*anthropic/d" | git commit --amend -F - -S' --root
```

Then retry `git push -u origin main`. If history was ever already pushed elsewhere, use `--force-with-lease` instead of `--force`.

## Diagnosis

`git log --format="%h %G? %s" -N` shows the signature status column. `G` = good signature, `N` = unsigned.
