# Pulling onto a dirty tree, and judging an old stash

## Read the procedure out of the remote, because a behind checkout's docs are behind too

The rule to consult `~/.claude/learnings/` before diagnosing anything assumes the file you reach is
current. That directory is a symlink into the dotfiles repo, so a stale checkout of *that* repo makes
every learning on the machine stale at once — and the failure is silent, because a missing file and a
subject nobody has written up are the same absence. A file that does not exist locally yet is exactly
the one a behind-and-dirty tree needs.

A fetch is enough to read it; no merge required:

```bash
git fetch -q
git show @{upstream}:claude/learnings/<topic>.md
git diff --name-status HEAD @{upstream} -- claude/learnings   # what else moved or arrived
```

Measured 2026-09-15: a checkout 21 commits behind had no local copy of this file at all, while
upstream's copy already held the path-scoped-stash recipe the situation called for. Reading it first
turned the pull into following a procedure rather than deriving one.

Whoever is behind cannot read this section locally either, so it only helps from the second time
onward — which is why the habit has to generalize past this file: **when a tree is behind, its
documentation is behind by the same commits.** Any doc consulted while catching up — a runbook, a
README, a migration note — is read from `@{upstream}`, not from the working tree.

## Fast-forwarding with uncommitted work in the way

Git refuses to fast-forward over a locally-modified file that the incoming commits also
touch, so a behind-but-dirty tree needs the work moved aside first:

```bash
git stash push -m "pre-pull local work"
git merge --ff-only origin/main
git stash pop --index
```

**Check whether the two sets actually intersect before reaching for the stash.** That refusal is
per-path: git fast-forwards a dirty tree without complaint as long as no incoming commit touches a
file you have modified. Compare them, and skip the stash entirely when nothing overlaps:

```bash
git diff --name-only | sort > /tmp/dirty
git diff --name-only HEAD @{upstream} | sort > /tmp/incoming
comm -12 /tmp/dirty /tmp/incoming     # empty → `git merge --ff-only` runs as-is
```

**When the dirty files are not yours, skipping the stash is the safer path rather than merely the
shorter one.** These repos are worked by several concurrent sessions, so a pull often finds edits in
the tree that another live session is partway through. A stash/pop lifts those edits off disk and
puts them back seconds later, and a session writing inside that window sees a file it did not
change — while an interrupted pop can leave them stashed rather than in the tree. With an empty
intersection nothing has to move at all. Verified 2026-09-02: eight incoming files against two dirty
ones, disjoint, and both dirty files hashed identical either side of the merge.

**A partial intersection wants a path-scoped stash, not a whole-tree one.** Between those two cases sits
the common one: a few dirty files overlap the incoming commits and most do not. Naming them keeps the
previous paragraph's answer even though the intersection is not empty, because everything outside the
overlap stays on disk and is never lifted:

```bash
git stash push -m "pre-pull local work" -- $(comm -12 /tmp/dirty /tmp/incoming)
git merge --ff-only origin/main
git stash pop --index
```

Verified 2026-09-11: seven dirty files against twenty-eight incoming, two of them overlapping. Stashing
only those two fast-forwarded cleanly, both popped back as a clean 3-way merge, and the other five were
never touched.

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

## The worst case makes no conflict at all

Both sections above are about a pop that *stops*. The case to fear is the one that succeeds: two
sides added the **same knowledge in different places**, so the hunks never touch and git has
nothing to report. Measured 2026-09-14 on a shared learnings file — one session appended a
"PrintWindow's alpha is not the window's transparency" section at line 108, another pushed the
same finding, in its own wording and with the same measured numbers, at the end of the file. The
pop applied clean, exit 0, and left one document asserting it twice.

Nothing mechanical catches this. A line check passes (no lines lost), a conflict check passes (no
conflict), and a diff against either parent looks like a normal addition. **The only instrument is
the table of contents**: after any pop or merge on a document, list its headings and read them for
two that mean the same thing.

```bash
grep -n '^#\{1,3\} ' <path>          # before the pop, and after
```

Two headings can differ in every word and still be one section — "`PrintWindow`'s alpha channel is
not the window's transparency" against "PrintWindow's alpha cannot tell you whether a window is
transparent" — so compare what they *claim*, not how they are spelled. Resolve by merging the two
into whichever one is better placed, taking each side's strongest parts; do not keep both and do
not pick a side, for the same reason the section above gives. The risk scales with how many
sessions write to one knowledge base, and it is highest exactly where the base is most useful.

**The same duplication happens across two files, where no table of contents can see it.** The check
above is per-document and assumes the duplicate is a *section*. A pull that **adds a file** on a
subject an existing file already covers yields two documents that are each internally coherent,
share no heading, and conflict in no line — so every instrument above reports clean. Measured
2026-09-14: a pull added a learnings file on cargo's target scope while an uncommitted one on cargo
warning gates sat in the tree, covering the same finding with the same measured probe table, reached
independently by two sessions. Neither `git status`, the merge output, nor either file's headings
said anything.

The instrument moves up one level, from the document's headings to the directory's filenames:

```bash
git diff --name-status <old-head> <new-head> | awk '$1=="A"{print $2}'   # what the pull added
```

Read each added file's title against the existing *filenames*, because a knowledge base indexed by
filename makes the same claim in its names that a document makes in its headings. The tell that two
files are one subject is that they **cite the same evidence** — two sessions reporting identical
measured numbers is duplication, not corroboration.

Resolving across files carries one hazard the within-document case cannot: deleting the loser breaks
every cross-reference pointing at it, including one you may have just written into the survivor
while merging. Grep for the deleted basename **after** the deletion, not before.

## A local migration that deletes the file upstream just appended to

Everything above assumes the contested file survives on both sides. The asymmetric case is a local
change that **removes** it — a format migration fanning one list file out into a directory of
per-item files, a config split, a document replaced by a folder — while upstream appended to the
old file because the other machine was still using it.

The trap is that the resolution looks settled. A path-scoped stash of the deleted file pops as a
modify/delete conflict, and the migration is plainly the newer design, so you keep the deletion —
and the appended item goes with it. Nothing objects, because every instrument is watching the wrong
thing: the file is *supposed* to vanish, so the conflict resolves cleanly; the stash-SHA baseline
lists that path as an incoming-commit file and calls it expected; and neither the heading check nor
the filename check applies to a document that no longer exists.

Don't pop. Reconcile by content, starting from what the migration was actually built against:

```bash
git show <pre-merge-head>:<old-path>   # the version the migration read
git show @{upstream}:<old-path>        # what upstream actually has
```

Carry each item present only in the second one into the new structure by hand, taking its sort key
from the item itself rather than from the clock — a migration that never saw the item has no
timestamp for it, and stamping it "now" silently reorders the result. Then assert per item, never on
a count:

```python
for item in old_items:
    hits = [p for p, text in new_files.items() if probe(item) in normalize(text)]
    assert len(hits) == 1, (item, hits)   # 0 = lost, 2+ = migrated twice
```

Verified 2026-09-14: the migration had produced four files from the four-item list it could see,
while upstream's copy of that list held five. The fifth came back only because the two sides were
compared item by item after the merge. A count check happens to catch that particular shape, and
stops working the moment one item is lost while another is migrated twice — which is why the
assertion above matches text rather than tallies.

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

**A path-scoped stash adds a second exception, and it is the noisier one.** The stash tree then records
`HEAD`'s version of every dirty file deliberately left out, so each one reads as a difference the merge
did not cause. Five appeared that way on 2026-09-11 and all five were benign. Union the unstashed dirty
paths into the expected set alongside the untracked ones, or verify those files by the claim that
actually matters — that the merge never touched them:

```bash
git diff --name-only <old-head> <new-head> -- <the unstashed dirty paths>   # empty → untouched
```

## Discarding untracked work safely: prove it is a function of what is committed

The sections above are about untracked or stashed work you must **keep**. The inverse case turns up
whenever a change was made by hand and never committed, and you now want the tested path to make it
instead: a hand-run migration, a scripted edit, a generated tree. `git checkout` cannot restore what
it never tracked, so `rm -rf` on that tree is the one genuinely irreversible step in the operation.

It is safe exactly when the tree is a deterministic function of committed state, and that is
provable rather than arguable. Rebuild it from the commit in a scratch clone and diff:

```bash
git -C "$repo" show HEAD:path/to/source > "$scratch/path/to/source"
# …run the same generator/migration against $scratch…
diff -rq "$scratch/generated" "$repo/generated"     # silence = nothing unique is at risk
```

Silence means every file is reproducible and no file exists that the rebuild would not produce — so
nothing was added, edited or removed since the hand run, and the delete costs nothing. Any output at
all is a reason to stop: a file only in the repo is work done afterwards, a file only in the scratch
tree means something was deleted afterwards, and a content difference is an edit.

Verified 2026-09-15 across five repos holding an uncommitted format migration. Two of them differed
by one byte — a `created:` second — because the hand migration had staggered two same-minute
timestamps to preserve line order while the scripted one wrote both as `:00`. That is the value of
diffing rather than spot-checking: a one-character difference in one file out of 54 was a real
ordering rule nobody had written down, and fixing the script to reproduce it turned all five into
byte-exact matches. Had the diff been skipped, the rule would have been discovered only as a
mysteriously reordered backlog weeks later.

Then restore the source with a **path-scoped** checkout, never a bare one — the tree is dirty by
premise and these repos routinely carry unrelated work:

```bash
git -C "$repo" checkout -- path/to/source && rm -rf "$repo/generated"
```

Capture `git status --short` before and after and diff the two. The only lines that may disappear
are the ones you meant to remove; anything else vanishing means the checkout was wider than intended.
