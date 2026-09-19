---
title: Every memo a checklist split produced sits on the side its marker asked for
---

## What changed

A backlog split by version 001 can be missing an open item with nothing saying so. This version is
the pass that finds it.

Version 001 routes an `[x]` checklist item into `memos/done/` and a `[ ]` item into `memos/`, then
asserts in its step 4 that every checklist line "appears in exactly one file under `memos/` or
`memos/done/`, matched on text". Presence anywhere under the backlog satisfies that `or`, so an item
routed into the wrong one of the two passes, and step 5 deletes the checklist that held the marker.
Matching on text is what makes the assertion blind: the `[x]` sits outside the text being matched,
so the check and the routing decision read different things and nothing compares them.

An open item filed as addressed then stops looking wrong and becomes absent. Nothing lists `done/` —
`memos.py list` and `show` both resolve against the open backlog — so the item appears in no
listing, while the file that would have contradicted it is gone.

Measured 2026-09-18 across every repo on this machine. Four had performed the split. In transcripts
and travel-map every marker matched its directory. The dotfiles repo put three files into a `done/`
whose checklist marked two, the extra being the memo that asked for the restructuring — the one
disagreement step 3 below sanctions. tauri-dashboard put 19 files into a `done/` whose checklist
marked 17: one was a `[ ]` line nobody ticked after the work it describes was finished, and one was
a file no checklist line ever covered. Both were moved back out of `done/` the same day, before this
version existed. Ten further repos that adopt conventions still hold `.claude/memos.md`, carrying 92
items between them, and each runs 001's frozen step 4 before it reaches this one; an eleventh copy
sits in a third-party clone, which adopts nothing and never arrives here.

Version 001 cannot be repaired in place. It is adopted in repos that will never re-run it, and the
gap is prose its migration reads, so editing it would give two repos different behaviour under one
number with the earlier one never finding out.

**This version carries no script, and that is a decision rather than an omission.** One was written
and thrown away. Matching a checklist line to the file it became looks mechanical and is not: the
stamp a line carries is only a prefix of the memo's `created:` field, since `memos.py` stores
seconds the checklist never held, and it is not unique either — four backlogs hold a same-minute
group whose members carry opposite markers, separated only by seconds 001 invented. Four rounds of
adversarial review found about 165 defects in three successive designs, and each design was blind
to something the previous one caught: joining on the stamp mistook an unrelated capture from the
same minute for a lost memo's file, and counting markers against sides reported two memos swapped
across those sides as correct, because the counts cancel.

What none of them could do is the thing the reader does without effort. A checklist line and the
memo it became are recognisably the same idea, even when 001's "Afterwards" step rewrote the title;
they are not the same string, and no rule over strings settles it. So the comparison below is read
rather than computed, by whoever is running the walk, against a list that is 5 items long in one
repo and 36 in the largest.

## Migrating an existing repo

**The prerequisite is one question: was this repo's backlog ever a `memos.md` checklist?** Where it
was, the split that replaced it is what this re-reads. Where it never was, the section below is the
whole of the work.

1. **Recover the checklist.** Find the commit that removed it, then read the file from that
   commit's parent:

   ```
   git log --full-history --diff-filter=D -1 --format=%H -- .claude/memos.md
   git show <that commit>^:.claude/memos.md
   ```

   Two answers are not a failure. Where the first command prints nothing but
   `git log --all --full-history --oneline -- .claude/memos.md` prints commits, the checklist lives
   on a branch this one cannot reach — check that branch out before going further. Where 001 has run
   in this same walk and nothing is committed, the file is gone from disk and still at `HEAD`:
   `git show HEAD:.claude/memos.md`. Both flags matter: without `--full-history` git prunes a side
   branch whose merge was TREESAME, which hides a checklist that two machines both edited.

   **Where git has no revision of it at all, stop and say so.** An untracked `.claude/memos.md`
   leaves exactly this trace once 001 deletes it, and the markers then exist nowhere — the only
   copy was the one 001 read minutes ago. Two repos that adopt conventions hold an untracked
   checklist as this is written, so this is a live state; ask the user rather than concluding the
   repo never kept a backlog. Committing `.claude/memos.md` before 001 runs is what prevents it.

   Read 001 Path A's last paragraph while you are here: it splits from the `@{upstream}` copy as
   well, so where `git show @{upstream}:.claude/memos.md` differs, an item present only there needs
   checking too.

2. **List the memos as the split left them.** Where the split is already committed, that is the
   tree of the commit that removed the checklist, not today's directory — a memo closed in the
   ordinary way since has moved into `done/` for a reason nobody should reopen:

   ```
   git ls-tree -r --name-only <the commit from step 1> -- .claude/memos/
   ```

   Where 001 ran in this walk, the working tree is that state: list `.claude/memos/` and
   `.claude/memos/done/` directly.

3. **Read the two lists side by side, and confirm each line against its memo.** An `[x]` item
   belongs in `done/`, a `[ ]` item in `memos/`. Match a line to a file by what they say rather
   than by their spelling; where several memos share a capture minute the filenames are the only
   thing that tells them apart, and where a title was rewritten during the split the stamp is.
   Write down every disagreement before moving anything, and decide each:

   - **A `[ ]` item in `done/`** is a misroute, unless that memo is the one that asked for the
     restructuring the split commit performed, which 001's Path B sanctions: such a memo is closed
     by performing it. Read it before allowing that — its title or its body has to name the work
     that commit did, and a one-line checklist item becomes a memo carrying a title and no body at
     all. In the dotfiles repo this is `improve-memos-by-storing-in-separate-files.md`, a title and
     nothing else, closed by `feat(memo): store one memo per file`.
   - **An `[x]` item in `memos/`** is the mirror misroute, and it has no sanctioned form.
   - **A line with no memo** is an item the split lost, which is the failure 001's step 4 does
     catch, so it should be empty. Where it is not, the line's full text is in the revision from
     step 1, and the memo is rebuilt from it with `created:` taken from the line's own stamp.
   - **A memo with no line** was captured directly in the new format while the migration was in
     progress, and nothing is wrong with it — unless it sits in `done/`, which is a closure nothing
     recorded, and the one case this version will not decide. Name the file and ask.

   Then check each disagreement against the backlog as it stands **now**, before repairing it. A
   memo already on the side its marker asks for was repaired since the split, by hand or by an
   earlier pass; repairing it again would undo that, and `memos.py reopen` resolves against `done/`,
   so on an already-reopened memo it fails rather than doing nothing.

4. **Repair through the helper**, which is available because the walk records 001's number before
   this version is read. Reopening is `python ~/.claude/skills/memo/memos.py reopen <slug>`; it
   re-derives the name from the title, so a close-date prefix goes without anything having to
   recognise or strip it. Closing is `memos.py done <slug>`.

   **What date a newly-closed memo takes depends on which case you are in, and the two rules
   disagree.** Where the split is already history, `memos.py done` stamps today, which is the day
   of the repair and not the day of the work — so recover the real close date with the pickaxe in
   001's Path B, searching at the precision the checklist line used rather than at the seconds
   `created:` carries, and `git mv` the file to it afterwards. Where 001 ran in this same walk,
   001's Path A governs instead and is explicit: its `[x]` items come out undated, named by slug
   alone, and inventing a date for one of them is forbidden. Rename the repaired file to drop the
   date there, so it matches its siblings and the count Path A asks for stays right.

Afterwards:

- **Read each memo you reopened in full.** A `[ ]` beside a body that describes the work as finished
  is a checklist nobody updated, not a split that routed wrongly — tauri-dashboard's Homebrew memo
  is exactly that, and it is still the marker that decides, because the marker is the only record of
  what anyone concluded. An item wrongly back in the open list costs one line in a listing; one
  wrongly in `done/` is what this version exists to find.
- **Say how many memos moved in the commit message**, not in `.claude/conventions`. That file holds
  one integer on one content line, the engine is its only writer, and a second line makes the repo's
  conventions state unreadable.

## When it does not apply

This repo's backlog was never a `memos.md` checklist. The positive evidence is
`git log --all --full-history --oneline -- .claude/memos.md` printing nothing, together with no
`.claude/memos.md` on disk. A `done/` full of memos still satisfies it — those were closed by
`memos.py done`, which writes both the directory and the date at the moment of the close. A repo
with no backlog at all is the same case and needs no separate answer.

Three readings of that same silence are not this case, and each is a question rather than an
absence.

- **A checklist that was never committed**, covered in step 1. The markers are unrecoverable once
  001 deletes it, and the two repos in that state need asking rather than reading.
- **A shallow clone.** Its grafted history answers the same way whatever the repo once held, so
  `git rev-parse --is-shallow-repository` is worth a look before believing the silence.
- **A git that would not answer** — an ownership refusal, a missing binary, a repository it will not
  open. An unanswered question must never read as a checklist that never existed.

## Continuing rule

None — this is a one-time migration, and no rule could carry it even in principle. The property is
about a change that happened once, measured against a checklist that exists only in a revision
receding with every commit. Nothing re-performs a split, so once this version has run, the answer
cannot change.
