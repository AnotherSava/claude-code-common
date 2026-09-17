---
title: memos.md becomes a memos/ directory
affects: memo
---

## What changed

The backlog was one checklist file. One memo is now one file under `.claude/memos/`, with `done/`
as a sibling directory instead of an `[x]` marker, so a memo can be as long as the idea needs and
listing one never parses a status. Frontmatter carries `created:`, so a future ordering is a field
rather than a rename. The format and its mechanics belong to the `memo` skill; this version only
moves what a repo already has. The `memos.py` helper reads the new layout only, so a repo still
holding `memos.md` has a backlog nothing can list — which is how one repo's sat unnoticed for two
days after the convention changed.

## Migrating an existing repo

There is work here when a `.claude/memos.md` sits on disk with no `.claude/memos/` beside it.

Fetch first, and do not run this on a branch behind its upstream. The migration deletes a file the
other machine may have appended to, and that deletion merges cleanly against the append, losing it
silently — `learnings/git-stash-pull-safety.md`. A dirty tree is not a reason to stop: several
repos hold this migration done and never committed, and there the record and the pending change
commit together, while `HEAD` still carrying the pre-migration file is what lets the per-item
assertion below run in full rather than be skipped.

Then:

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

What the deletion loses, and how to compare it: `memos.md` carries header lines describing the
format being retired, and they go deliberately — read them before the file does, since afterwards
they exist only in git history. Diff the new files against `git show HEAD:.claude/memos.md`, and if
the file still differs between `HEAD` and `@{upstream}`, read `git show @{upstream}:.claude/memos.md`
as well and carry each item present only upstream into its own file.

Afterwards:

- Run `git check-ignore -v .claude/memos/`. A repo excluding `.claude/` wholesale leaves every new
  file untracked, and a `!.claude/memos/` re-include inside a wholly-excluded directory does
  nothing; the entry has to become `.claude/*` plus explicit `!` re-includes.
- Read the resulting titles. A one-line checklist item becomes a one-line memo with no body, and
  several are usually worth expanding while the context is still there.

Three states are a question for the user rather than work to do:

- **Both files exist** — a half-finished migration. Which side is authoritative is not this
  version's guess, so name the items that are in `memos.md` only and would be lost if it were
  simply deleted, and leave the resolution to a human.
- **No backlog anywhere, and `HEAD` still carries `.claude/memos.md`** — the backlog is currently
  nowhere: the file was deleted and nothing replaced it. Restore it with
  `git checkout HEAD -- .claude/memos.md` and start again, or confirm it was emptied deliberately.
- **No backlog anywhere, and `HEAD` never carried one** — does this repo want a backlog at all?
  Never create one, because an empty `.claude/memos/` is cruft, and a stray empty directory already
  on disk is worth deleting either way.

Each of those reads `HEAD`, so a git that will not answer — an ownership refusal, a missing binary
— belongs in the question rather than folded into "`HEAD` never carried one", which would turn a
deleted backlog into one that was never kept.

## When it does not apply

The backlog is already a directory holding at least one memo file, with no `.claude/memos.md`
beside it. Read both halves before concluding it: the directory listing and the absence of the old
file together are what make a first record cost nothing in the repos that migrated ad hoc before
this version existed.

A directory holding no memo file is not that case. An empty directory is a shell rather than a
migrated backlog, and it goes to the questions above.

Absence is never a reason to skip either. A repo holding neither file has not been shown to want no
backlog — several repos deliberately keep none, and that is indistinguishable from a migration
nobody ran, so it too goes to the questions above.

## Continuing rule

None — this is a one-time migration.
