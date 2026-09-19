# Finding a file that is no longer in the tree

Asking git where a deleted file used to live has two traps, and both answer confidently. One hides
a whole branch's worth of history; the other makes "the file is not there" and "git will not tell
you" arrive as the same exit code. A tool that reads either of them wrong concludes the file never
existed, which is the worst available answer — it looks like a clean result rather than a failure.

## A path-limited log prunes the branch you are looking for

By default `git log` and `git rev-list` apply history simplification: when a merge is TREESAME to
its first parent for the path you asked about, git follows only that parent and the side branch
disappears. So a file that was created, edited and deleted entirely on a feature branch is
invisible after the merge, and so is a copy that a second machine edited before the merge resolved
in favour of the deletion.

```
git rev-list HEAD -- <path>                   # simplified: misses the side branch
git rev-list --full-history HEAD -- <path>    # every revision that touched it
git log --all --full-history --oneline -- <path>
```

Measured 2026-09-18 on a fixture built from the real shape: a checklist split on `main` while the
other machine appended to it, the merge keeping the deletion. The simplified form returned the
older two-commit view and a tool reading it compared against a stale copy, reporting a repo with a
real defect as clean. With `--full-history` the reachable four-commit view includes the newer copy.
The same flag belongs on the "did this file ever exist here" probe, not only on the one that reads
it: without it, a repo whose whole backlog lived on a merged-and-deleted branch answers "no
revision ever carried this" while the blobs are still perfectly reachable.

This is the same family as the pickaxe trap in `git-dating-a-file-from-history.md` — a real commit,
a real answer, the wrong event.

## `cat-file -e` cannot tell absence from refusal

The obvious existence probe is wrong:

```
git cat-file -e <rev>:<path>     # 128 when the path is missing from an existing tree
                                 # 128 when git declines to open the repo at all
```

Both are 128, so an exit-code test either misses the absence or turns an ownership complaint, a
missing binary or a broken repository into "the file is not there". Ask a command whose *output*
carries the answer instead, and let any non-zero exit stay a refusal:

```
git ls-tree --name-only <rev> -- <path>    # empty output = absent; non-zero exit = refusal
```

Resolve the revision separately, so the probe is left answering one question:
`git rev-parse --verify --quiet <rev>^{commit}`. That also keeps `@{upstream}` honest — a branch
with no upstream configured fails there, which is an absent source rather than a git that refused.

## A shallow clone answers the same way as an empty history

`git rev-parse --is-shallow-repository` is worth asking before believing any silence, because the
graft point makes an arbitrarily rich history look like none at all. Same for a repo with no
commits: `HEAD` does not resolve, and a probe that treats that as "nothing found" reports a verdict
about a repository it never read.
