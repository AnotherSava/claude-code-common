---
title: The memo backlog is a directory, and addressed memos carry their close date
---

## What changed

The backlog was one checklist file. One memo is now one file under `.claude/memos/`, with `done/`
as a sibling directory instead of an `[x]` marker, so a memo can be as long as the idea needs and
listing one never parses a status. Frontmatter carries `created:`, so a future ordering is a field
rather than a rename. The `memos.py` helper reads the new layout only, so a repo still holding
`memos.md` has a backlog nothing can list — which is how one repo's sat unnoticed for two days
after the convention changed.

An addressed memo is never deleted: the record of what was decided is the cheapest thing in a repo
to keep and the only part of a backlog that cannot be rebuilt. That makes `done/` append-only, and
nothing in the memo skill lists it — `list` and `show` both resolve against the open backlog. Its
readers are a file browser, `ls` and `git status`, and a name is the only thing any of those sorts
by, so the close date goes into the name. That is the one place this backlog inverts its own rule
that a sort key lives in metadata rather than in an identifier, and the trade is stated rather than
hidden: a second ordering over done memos would cost a rename of them all, accepted because there
is no reader to give a field to.

Going forward nothing re-asserts either half. `cmd_done` in `memos.py` writes the dated name at the
moment a memo is closed, and every command reads the directory layout only.

## Migrating an existing repo

**The prerequisite is one question: does this repo have a backlog at all?** If it does, everything
below applies to it; if it does not, the questions at the end are the whole of the work. Read both
`.claude/memos.md` and `.claude/memos/` before deciding which path you are on — they are mutually
exclusive in a healthy repo, and holding both is one of the questions.

Fetch first, and do not run this on a branch behind its upstream. The migration deletes a file the
other machine may have appended to, and that deletion merges cleanly against the append, losing it
silently — `learnings/git-stash-pull-safety.md`. A dirty tree is not a reason to stop: several
repos hold this migration done and never committed, and there the record and the pending change
commit together, while `HEAD` still carrying the pre-migration file is what lets the per-item
assertion below run in full rather than be skipped.

### Path A — `.claude/memos.md` is on disk

1. Read `.claude/memos.md` in full and split it. Every checklist item becomes one file under
   `.claude/memos/`, or under `.claude/memos/done/` where the item is marked `[x]`, named after a
   slug of its title, with frontmatter carrying `created:`.
2. Take each `created:` from the item's own timestamp and never from the clock — stamping "now"
   silently reorders the backlog. An item carrying a date and no time keeps the bare date, because
   the hour it was captured is recorded nowhere and this migration invents nothing; `memos.py`
   reads, shows and orders it without complaint, placing it before every timestamped memo of the
   same day.
3. Stop on a content line that reads as neither an item, a continuation of the item above it, nor
   the file's own header. Print it verbatim with its line number and write nothing, leaving
   `memos.md` untouched. That is not fussiness — the first script written for this recognised one
   line shape and silently skipped the rest, then deleted the file while reporting that every item
   had been found.
4. Before deleting anything, assert per item: every checklist line in `memos.md` appears in exactly
   one file under `memos/` or `memos/done/`, matched on text. Zero hits means the item was lost,
   two that it was migrated twice, and a tally passes the moment one of each happens. A line the
   reading in step 3 could not classify is not asserted and fails the migration, because an
   unasserted line must never read as a passed one.
5. Delete `.claude/memos.md` only once that assertion holds. The source file survives every
   failure, so a re-run after an interrupted attempt picks up the memos already written.

**The `[x]` items come out undated, and that is the honest answer rather than a gap.** A close date
has exactly one truthful source — the commit that put a file at its `done/` path — and a split
performed today never produced one. The dates available are all wrong: `created:` is when the idea
was captured, and today is when the migration ran. Name those files by slug alone, and say in the
record how many carry no date. They sort alphabetically and say nothing about when anything was
decided, which is the position every repo was in before this convention existed. Offer the user the
chance to supply real dates by hand; never invent one.

What the deletion loses, and how to compare it: `memos.md` carries header lines describing the
format being retired, and they go deliberately — read them before the file does, since afterwards
they exist only in git history. Diff the new files against `git show HEAD:.claude/memos.md`, and if
the file still differs between `HEAD` and `@{upstream}`, read `git show @{upstream}:.claude/memos.md`
as well and carry each item present only upstream into its own file.

### Path B — `.claude/memos/` exists and `done/` holds undated names

There is work here when `done/` holds at least one `.md` file whose name does not open with a real
`YYYY-MM-DD-` prefix, and git can say when each of those was closed. The close date is the date the
commit that added the file at its `done/` path was authored:

```
git log --diff-filter=A --format=%ad --date=format:%Y-%m-%d -- .claude/memos/done/<name>
```

Take the first line, newest first — a memo closed, reopened and closed again was added there more
than once, and the close that matters is the one whose result is on disk now. Ask for no rename
detection: the move into `done/` *is* the addition this reads, and `-M` would resolve it back to the
open path and answer with the capture date instead.

Then `git mv` each file to that date plus `-` plus its existing name, and check the bytes are
identical at the new name and gone from the old one.

### Afterwards, on either path

- Run `git check-ignore -v .claude/memos/`. A repo excluding `.claude/` wholesale leaves every new
  file untracked, and a `!.claude/memos/` re-include inside a wholly-excluded directory does
  nothing; the entry has to become `.claude/*` plus explicit `!` re-includes.
- Read the resulting titles. A one-line checklist item becomes a one-line memo with no body, and
  several are usually worth expanding while the context is still there.
- **Whether each recovered date is the right one.** The rename asserts that a name opens with a real
  date and that the bytes survived; it cannot know whether the commit that added a file to `done/`
  is the moment the work was actually finished. A memo closed in one session and committed a week
  later carries the commit's date, and only a person can say that matters.
- **A memo whose own slug begins with a date.** A title like "2026 09 15 was the day the job
  stopped" derives a slug opening with `2026-09-15-`, which reads as already dated and is left
  alone. It is rare and harmless — the name still sorts — but the date is the title's, not the
  close's.

### States that are a question rather than work

- **Both `memos.md` and `memos/` exist** — a half-finished migration. Which side is authoritative is
  not this version's guess, so name the items that are in `memos.md` only and would be lost if it
  were simply deleted, and leave the resolution to a human.
- **No backlog anywhere, and `HEAD` still carries `.claude/memos.md`** — the backlog is currently
  nowhere: the file was deleted and nothing replaced it. Restore it with
  `git checkout HEAD -- .claude/memos.md` and start again, or confirm it was emptied deliberately.
- **No backlog anywhere, and `HEAD` never carried one** — does this repo want a backlog at all?
  Never create one, because an empty `.claude/memos/` is cruft, and a stray empty directory already
  on disk is worth deleting either way.
- **A done memo git has never seen**, on path B. Its close date is unreadable, because the only
  honest source is the commit that put it in `done/` — an mtime is rewritten by a clone, a checkout
  or a rebase and answers when this machine last wrote the file. Print the names and ask: commit the
  close first and start again, or rename those by hand.
- **A name opening with something date-shaped that is not a date** — `2026-13-45-foo.md`. It is
  neither dated nor plainly undated, and this version will not decide which. Name the files and ask
  for a real close date or a bare slug. Treating such a name as already-dated would record the repo
  conformant on a name no reader can order, and treating it as undated would prefix a second date.

Each of the first three reads `HEAD`, so a git that will not answer — an ownership refusal, a
missing binary — belongs in the question rather than folded into "`HEAD` never carried one", which
would turn a deleted backlog into one that was never kept.

## When it does not apply

The backlog is already a directory holding at least one memo file, with no `.claude/memos.md`
beside it, and every name in `done/` opens with a real date — parsed as a date rather than merely
matched for shape. Read all three halves before concluding it: the directory listing, the absence of
the old file, and the names in `done/` together are what make a first record cost nothing in the
repos that migrated ad hoc before this version existed.

A `done/` holding no memo at all satisfies the third half on its own. Count the open backlog and
report it alongside, so the reading says a backlog was read and had nothing addressed in it yet.

A directory holding no memo file is not this case. An empty directory is a shell rather than a
migrated backlog, and it goes to the questions above.

Absence is never a reason to skip. A repo holding neither file has not been shown to want no
backlog — several repos deliberately keep none, and that is indistinguishable from a migration
nobody ran, so it too goes to the questions above.

## Continuing rule

None — this is a one-time migration.
