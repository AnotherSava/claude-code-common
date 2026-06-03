---
name: stash-pop conflict --theirs is the stash, not the upstream
description: During git stash pop, --ours = post-pull working tree; --theirs = the stash. When unsure, use `git checkout <ref> -- <file>` instead of side-flags.
type: feedback
---

When resolving a conflict mid-`git stash pop`:
- `--ours` refers to the **working-tree state after the pull** (the upstream side you just pulled into).
- `--theirs` refers to the **stash** (your local changes being applied).

This is opposite to what "theirs = upstream" intuition suggests, and easy to get wrong — I burned a tool call this way during a release-prep pull.

**Why:** Stash-pop is a merge where HEAD ("ours") is whatever's already on disk and the stash ("theirs") is the incoming side. Consistent with `git merge` semantics, but rarely thought of through that lens.

**How to apply:** When in doubt, don't guess `--ours`/`--theirs`. Use `git checkout <ref> -- <file>` to grab the file from a specific named source (`origin/main`, the stash sha, etc.) — bypasses the side-confusion entirely.
