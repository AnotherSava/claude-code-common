---
version: 1
slug: memos-directory
title: memos.md becomes a memos/ directory
scope: repo
---

# memos.md becomes a memos/ directory

The backlog was one checklist file. One memo is now one file under `.claude/memos/`, with
`done/` as a sibling directory instead of an `[x]` marker, so a memo can be as long as the
idea needs and listing one never parses a status. Frontmatter carries `created:`, so a
future ordering is a field rather than a rename. The format and its mechanics belong to the
`memo` skill; this step only moves what a repo already has. The `memos.py` helper reads the
new layout only, so a repo still holding `memos.md` has a backlog nothing can list — which
is how one repo's sat unnoticed for two days after the convention changed.

## Applies when

A `.claude/memos.md` sits on disk with no `.claude/memos/` beside it.

## Does not apply when

The backlog is already a directory holding at least one memo file, with no `.claude/memos.md`
beside it. Verify sees that first and records the repo as in the target shape without touching
anything, which is what makes a first record cost nothing in the repos that migrated ad hoc
before this step existed; probe repeats the same reading for anyone who runs it directly.

A directory holding no memo file is not that case. Verify fails on exactly that tree, so probe
answering "does not apply" there would file the repo as never needing a convention its own
verify has just refused it. An empty directory is a shell, not a migrated backlog, and it goes
to the question below.

Absence is never a reason to skip. A repo holding neither file has not been shown to want no
backlog — several repos deliberately keep none, and that is indistinguishable by probe from
a migration nobody ran. That case is a question, below.

## Cannot tell

Three states, each asking something different:

- **Both files exist** — a half-finished migration. Which side is authoritative is not this
  step's guess, so probe names the items that are in `memos.md` only and would be lost if it
  were simply deleted, and leaves the resolution to a human.
- **No backlog anywhere, and `HEAD` still carries `.claude/memos.md`** — the backlog is
  currently nowhere: the file was deleted and nothing replaced it. Restore it with
  `git checkout HEAD -- .claude/memos.md` and re-run this step, or confirm it was emptied
  deliberately.
- **No backlog anywhere, and `HEAD` never carried one** — does this repo want a backlog at
  all? This step never creates one, because an empty `.claude/memos/` is cruft. Record `n/a`
  when the absence is deliberate. An empty `.claude/memos/` already on disk is named in the
  question, since a stray directory is worth deleting either way.

Each of those reads `HEAD`, so a git that will not answer — an ownership refusal, a missing
binary — is reported as part of the question rather than folded into "`HEAD` never carried
one", which would turn a deleted backlog into one that was never kept.

A fourth case stops `apply` rather than probe: a content line the parser cannot read as an
item, as a continuation of the item above it, or as the file's own header. It is printed
verbatim with its line number, nothing is written, and `memos.md` is untouched. That is not
fussiness — the first draft of this script recognised one line shape and silently skipped
the rest, then deleted the file while reporting that every item had been found.

## Fetch before running

This step deletes a file the other machine may have appended to, and that deletion merges
cleanly against the append, losing it silently — `learnings/git-stash-pull-safety.md`. The
`/adopt` procedure refuses to start on a branch behind its upstream, which is the gate that
matters here.

A dirty tree is not a reason to refuse. Several repos hold this migration done and never
committed; there the record line and the pending change commit together through `/commit`,
and `HEAD` still carrying the pre-migration file is what lets the per-item assertion run in
full rather than being skipped.

If the file still differs between `HEAD` and `@{upstream}` afterwards, compare
`git show @{upstream}:.claude/memos.md` against what was written, and carry each item
present only upstream into its own file — taking `created:` from the item's own timestamp
and never from the clock, since stamping "now" silently reorders the backlog.

## Verify

The question is whether this repo is in the shape the convention requires, never whether a
migration ran here. Asking the second inverts the answer on exactly the repos that did the
work: committing the migration takes `memos.md` out of `HEAD`, so a check keyed on reading
it back reports that it cannot tell, `/adopt` falls through to probe, and repos already in
the target shape get recorded as never having applied.

So the assertion is: no `.claude/memos.md` on disk, and `.claude/memos/` holding at least
one memo file. An empty directory fails — a check that passes on one cannot tell done from
never-run.

Where `HEAD` still carries `.claude/memos.md`, one more assertion runs on top of that shape:
every checklist line in the committed file appears in exactly one file under `memos/` or
`memos/done/`, matched on text. Zero hits means the item was lost, two that it was migrated
twice, and a tally passes the moment one of each happens. A line in `HEAD` the parser cannot
classify is reported as `NOT ASSERTED` and fails the check, because an unasserted line must
never read as a passed one.

The same per-item assertion is what `apply` runs, in its own process, before it removes
anything — the source file survives every failure, and a re-run picks up the memos an
interrupted attempt already wrote.

Exit 2 is reserved for the one thing that cannot be observed at all: no `.claude/memos/` to
read.

A git that will not answer what `HEAD` carries — an ownership refusal, a missing binary — is
exit 3 and not exit 2. The shape is observable; what could not be run is the stronger
assertion on top of it, and exit 2 would send `/adopt` on to probe, which reports the
directory and files the repo as never needing the step at all.

## By hand, after the script

- Run `git check-ignore -v .claude/memos/`. A repo excluding `.claude/` wholesale leaves
  every new file untracked, and a `!.claude/memos/` re-include inside a wholly-excluded
  directory does nothing; the entry has to become `.claude/*` plus explicit `!` re-includes.
- Read the header lines the run reported as not carried over. They describe the format being
  retired and are dropped deliberately, so anything real among them now exists only in git
  history.
- Read the resulting titles. A one-line checklist item becomes a one-line memo with no body,
  and several are usually worth expanding while the context is still there.
- Check any item that carried a date and no time. It keeps the bare date as its `created:`,
  because the hour it was captured is recorded nowhere and this step invents nothing;
  `memos.py` reads, shows and orders it without complaint, placing it before every
  timestamped memo of the same day.
