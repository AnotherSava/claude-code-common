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

## A file that is one enormous line breaks every assumption above

"Non-overlapping edits to the same file merge cleanly" is a statement about *lines*. A file
whose content is one gigantic line — a prose paragraph kept unwrapped, minified output,
single-line JSON — has no line granularity, so two edits to completely unrelated sentences
land in the same hunk and **always** conflict. The markers are worse than useless: git wraps
the whole line twice, producing a conflict region tens of thousands of characters wide whose
two versions differ somewhere in the middle. There is nothing to resolve by hand.

Don't pop. Re-apply instead:

```bash
git stash push -m "local edits" -- bigfile.md
git merge --ff-only origin/main
# then re-apply each local edit as an exact-string replacement against the NEW text
git stash drop
```

This works because the local edits are known string replacements, and upstream's version
still contains the original strings whenever the two sides touched different sentences. Check
that first — `git show origin/main:bigfile.md | grep -c "<the exact old sentence>"` returning
1 means the replacement is still valid and upstream did not revise the same passage.

**Verify by structural equality, not by reading a diff.** A character-level differ
(`difflib.SequenceMatcher`) over two 75k-character lines fragments into dozens of one- and
two-character regions that mean nothing — it finds spurious common substrings everywhere. The
honest check reconstructs what the file *should* be and compares bytes:

```python
expected = upstream_text
for old, new in my_edits:
    assert expected.count(old) == 1     # catches a passage upstream also revised
    expected = expected.replace(old, new)
assert expected == current_text
```

If that fails, blank out each edited region in *both* texts (replace it with a sentinel) and
compare the skeletons — identical skeletons prove nothing outside the local edits differs
from upstream, which is the actual merge-correctness claim. The stash-SHA baseline under *A
dropped stash is still recoverable* is the whole-tree version of the same idea, and is the
better check once more than one file is in play.

## When both sides rewrote the same rule

The both-append case has a twin that is indistinguishable in `git status` and is not mechanical
at all: both sides *replaced* the same passage instead of appending to it, because two machines
grew one document along different axes. Keeping both blocks verbatim yields a file that
contradicts itself; taking a side silently discards a body of work. Neither is the answer.

The tell is a **dangling cross-reference in the region that merged cleanly**. Auto-merge only
touches lines one side left alone, so a sentence that survived untouched while pointing at a
section living in just one of the two conflicted blocks proves that neither block is complete by
itself. Real case: a skill's step-4 heading read "go straight to the missing-shot pass below".
That heading auto-merged from the local side; the pass it names existed only in the local block,
while upstream had rewritten the surrounding bullets around a different design. Taking upstream
wholesale would have left the reference pointing at nothing.

Resolve by asking what *layer* each side worked at, not which lines to keep. Pull the three
stages out and diff each against the base — that separates "what did upstream add" from "what
did I add" far better than reading the marked-up file, where the two are interleaved:

```bash
git ls-files -u -- <path>            # stage 1 = base, 2 = ours/upstream, 3 = theirs/stashed
git cat-file -p <stage-1-sha> > /tmp/base.md
git cat-file -p <stage-2-sha> > /tmp/ours.md
git cat-file -p <stage-3-sha> > /tmp/theirs.md
diff -u /tmp/base.md /tmp/ours.md    # upstream's axis
diff -u /tmp/base.md /tmp/theirs.md  # the local axis
```

Read that way, most of the apparent conflict is usually complementary — in that case one side had
built a governance layer (a manifest, a per-item policy) and the other the capability that layer
presupposed but never specified. Only a small core genuinely disagreed. Merge the complementary
parts yourself and put the real disagreement to the user rather than settling it: it is a question
about their rules, not a merge mechanic. Verify afterwards by grepping the merged file for a
distinctive phrase from each side and *counting* the hits, so a silent duplication shows up
alongside a silent loss.

**Triage several conflicts at once before reading any of them.** The dangling-cross-reference tell
above is per-file and subtle; a cheaper first screen sorts a whole pop's worth in one command. Print
each half's section headings — or its bold bullet leads — tagged by side:

```bash
awk '/^<<<<<<</{s="UPSTREAM";next} /^=======$/{s="LOCAL";next} /^>>>>>>>/{s="";next}
     s && /^#{2,3} /{print "  ["s"] "$0}' <file>
```

**Disjoint** heading sets mean both sides appended different sections: mechanical, keep both. **Overlapping**
sets mean they rewrote the same material: stop and read. Four conflicts sorted into three mechanical and one
design decision this way, in one pass.

**Assemble a merge by extracting whole bullets verbatim from each half, never by retyping.** Split the region
into `up.txt` and `loc.txt`, then build the result by pulling each bullet out by its marker text. Retyping
introduces drift nobody can audit, and the extract-and-order form makes the important question — *which
bullets did I drop* — answerable by listing what was not selected.

**Expect the whole-patch line check to report the dropped duplicates as missing, and say so.** The stash-SHA
baseline below is the right verification for a mechanical resolution and is *wrong to trust blindly* here: an
editorial merge deliberately discards each side's superseded bullet, so those lines are legitimately absent
and the check counts them as losses. Report the count with its explanation rather than letting it read as a
failure — or, worse, "repairing" it by pasting the duplicates back. This is the one resolution a mechanical
check cannot vouch for, which is why the merged block goes in front of the user.

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
