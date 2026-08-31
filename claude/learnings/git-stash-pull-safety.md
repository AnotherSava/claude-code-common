# Pulling onto a dirty tree, and judging an old stash

## Fast-forwarding with uncommitted work in the way

Git refuses to fast-forward over a locally-modified file that the incoming commits also
touch, so a behind-but-dirty tree needs the work moved aside first:

```bash
git stash push -m "pre-pull local work"
git merge --ff-only origin/main
git stash pop --index
```

**`--index` is the part that's easy to miss.** A plain `git stash pop` restores everything
as *unstaged*, silently flattening the staged/unstaged split. That destroys real
information whenever the index held something deliberate — a staged file deletion, or a
file both staged and further modified (`MM` in `git status --short`). `git pull --rebase
--autostash` has the same flaw: its internal pop doesn't restore the index either. Use the
explicit three-step form whenever the left column of `git status --short` is non-blank.

Two things that are less fragile than they look:

- **Stash pop is a real 3-way merge, not a checkout.** Non-overlapping edits to the same
  file merge cleanly — a local append at the end and an incoming insert near the top
  produce no conflict.
- **`git stash push` leaves untracked files alone**, so they survive the fast-forward
  untouched. The one hazard is an incoming commit that *adds* a path matching an existing
  untracked file; check the incoming file list for collisions first.

The conflict you *will* get, over and over, is the mirror image of the first bullet: **both
sides appending to the end of the same list.** An index file, a changelog, a bullet list that
every session grows from the bottom — two appends at the same anchor always collide, however
unrelated their content. Nothing about the resolution is ambiguous, so treat it as mechanical
rather than as a fresh judgement call each time: keep both blocks, upstream first, and delete
the three marker lines. Then confirm both sides survived, since "kept both" is exactly the
claim a careless edit silently breaks.

## Clearing the merge state after a conflicted pop

A `git stash pop` that conflicts **keeps the stash entry** ("The stash entry is kept in case
you need it again"), so dropping it is a separate, deliberate step once the resolution is
verified. Until then the conflicted paths sit in the index as `UU` while everything else in
the tree is unstaged. Marking them resolved means `git add`, which also stages them — leaving
a tree split between staged and unstaged work that nobody asked for. A bare `git reset`
(mixed, no paths) afterwards clears the unmerged entries *and* the staging without touching
the resolved content in the working tree:

```bash
git add path/one.md path/two.md   # marks resolved
git reset -q                      # back to an all-unstaged tree
git stash drop
```

Worth doing wherever the repo's convention is that nothing is staged until a commit flow
runs — a half-staged tree reads as deliberate intent to the next thing that looks at it.

## Is an old stash still worth keeping?

`git apply --check` (and `--check -R`) is a poor staleness test. Once surrounding lines
have drifted, the patch fails to apply in *both* directions, which says nothing about
whether the content is already present — only that the context no longer lines up.

Test the content instead: extract the stash's added lines and look for them in the current
tree, per file.

```bash
git stash show -p 'stash@{0}' > /tmp/s.patch
# then, per '+++ b/<file>' section, count how many '+' lines appear in `git show HEAD:<file>`
```

A stash whose added lines are essentially all present in `HEAD` was already committed by
another route and is safe to drop. Two caveats when scoring this:

- Compare with **set semantics** — a line duplicated in the patch appears once in the
  file, so a naive `present/total` count under-reports and invents phantom "missing" lines.
- Ignore short lines (blanks, `` ``` ``, `-`); they match everywhere and inflate the score.

## A dropped stash is still recoverable — and useful as a baseline

`git stash drop` removes only the *ref*. The commit object survives in the object database
until garbage collection, so printing the SHA first makes the drop reversible:

```bash
SHA=$(git rev-parse 'stash@{0}')
git stash drop
git stash apply "$SHA"   # still works
```

The same property makes a stash commit the best verification baseline after a
stash/pull/pop cycle. The stash tree *is* the pre-pull working tree, so

```bash
git diff <stash-sha> -- .
```

should list exactly the incoming commits' files and nothing else. Any local edit the merge
mangled shows up here. This checks the whole tree in one command, which hand-reconstructed
before/after patches do not — and it sidesteps the easy mistake of diffing two slices that
don't actually correspond.

**Untracked files are the exception to "nothing else".** A plain `git stash push` never
captured them, so they are absent from the stash tree and every one of them appears in that
diff as an addition. Union them into the expected set before asserting the diff is clean, or
the check cries wolf on files it was never watching:

```bash
git diff --name-only "$SHA" -- . | sort -u > /tmp/actual
{ git diff --name-only "$SHA^" @{upstream} -- .; git ls-files --others --exclude-standard; } |
  sort -u > /tmp/expected
comm -23 /tmp/actual /tmp/expected     # anything printed here is genuinely unexplained
```
