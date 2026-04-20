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

## File removal from history

Same `git rebase --exec` shape works for removing a file (or editing content) from every commit in a range, not just signing. Useful when a file was committed that shouldn't have been (accidentally-tracked build artifact, upstream-licensed file that needs to be purged, leaked secret).

Write a tiny shell script that removes the file if present and amends the commit (amend `-S` re-signs as a side effect):

```bash
# /tmp/strip.sh
#!/bin/bash
set -e
if git ls-files --error-unmatch path/to/file > /dev/null 2>&1; then
    git rm path/to/file
    git commit --amend --no-edit -S
fi
```

Then:

```bash
git branch backup-main                                   # safety net
chmod +x /tmp/strip.sh
git rebase --exec /tmp/strip.sh <first-bad-commit>~      # replays and re-signs the range
```

The rebase picks each commit in order; after each pick the script runs in the worktree, removes the file if the pick brought it in, and amends+signs. Subsequent commits in the same range that don't touch the file pick cleanly on top of the rewritten tree and the script is a no-op.

Once you've verified the rewrite looks right and tests pass, drop the safety net and make the removal permanent in the object database:

```bash
git branch -D backup-main
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

`git log --all --full-history -- path/to/file` should return empty after this.

If the range has already been pushed, replay will change every commit's hash and you'll need `git push --force-with-lease` — coordinate with any collaborators first.

## Diagnosis

`git log --format="%h %G? %s" -N` shows the signature status column. `G` = good signature, `N` = unsigned.
