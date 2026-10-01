---
name: feedback_fork_over_carried_patches
description: Once local patches to a third-party clone outlive their session, fork and branch them rather than carrying them uncommitted
metadata:
  type: feedback
---

Once a local change to a third-party clone outlives the session that made it, fork the repo and
put the change on a branch. Do not keep accumulating patches in the working tree.

**Why:** an uncommitted patch in a clone is lost in two ordinary ways and neither announces
itself. A pull collides with it, and reinstalling the project from a release — or recloning —
drops it silently while the built artifact goes on reporting the upstream version, so the fix
appears to be present long after it is gone. The user asked for the fork on 2026-10-01 after the
third patch accumulated in an agwinterm clone, having been told twice that the previous two were
being "carried": the second telling is the signal that the structure is wrong rather than the
risk being worth restating.

**How to apply:** fork it, rename the existing remote to `upstream` and point `origin` at the
fork, then commit one patch per commit on a `local` branch. `/pull` then means fetching
`upstream` and rebasing, so a collision surfaces as a rebase conflict instead of a dirty tree.
Anything worth proposing upstream cherry-picks from there onto a clean topic branch off
`upstream/main`, which also keeps local-only files — a `.claude/` directory, a per-machine
wrapper — off any pull request. Where the build stamps a version, give the fork's builds a mark
of their own so an installed patched build cannot be mistaken for the release.

This does not loosen [[agwinterm-is-third-party]]-style rules about landing nothing in someone
else's tree: the fork is the user's, and `upstream` stays untouched.
