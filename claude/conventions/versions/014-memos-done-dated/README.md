---
title: Addressed memos carry their close date at the front of the name
scope: repo
---

## What changed

An addressed memo is never deleted — the command that used to clear `.claude/memos/done/` is gone,
because the record of what was decided is the cheapest thing in a repo to keep and the only part of
a backlog that cannot be rebuilt. That makes `done/` append-only, and nothing in the memo skill
lists it: `list` and `show` both resolve against the open backlog. Its readers are therefore a file
browser, `ls` and `git status`, and a name is the only thing any of those sorts by.

So the close date goes into the name, which is the one place the backlog inverts its own rule that a
sort key lives in metadata rather than in an identifier. The trade is stated rather than hidden: a
second ordering over done memos would cost a rename of them all, and that is accepted here because
there is no reader to give a field to. Repos adopted before this hold done memos named by slug
alone, which sort alphabetically and say nothing about when anything was decided.

It hands the checker nothing, because the writing side already carries it: `cmd_done` in
`memos.py` puts the date on the front of the name at the moment a memo is closed, so every name
written after this version is in the shape without anything re-asserting it.

## Migrating an existing repo

There is work here when `.claude/memos/done/` holds at least one `.md` file whose name does not open
with a real `YYYY-MM-DD-` prefix, and git can say when each of those was closed.

The close date is the date the commit that added the file at its `done/` path was authored:

```
git log --diff-filter=A --format=%ad --date=format:%Y-%m-%d -- .claude/memos/done/<name>
```

Take the first line, newest first — a memo closed, reopened and closed again was added there more
than once, and the close that matters is the one whose result is on disk now. Ask for no rename
detection: the move into `done/` *is* the addition this reads, and `-M` would resolve it back to the
open path and answer with the capture date instead.

Then `git mv` each file to that date plus `-` plus its existing name, and check the bytes are
identical at the new name and gone from the old one.

Two states are a question for the user rather than work to do:

- **A done memo git has never seen.** Its close date is unreadable, because the only honest source
  is the commit that put it in `done/` — an mtime is rewritten by a clone, a checkout or a rebase
  and answers when this machine last wrote the file. Print the names and ask: commit the close first
  and start again, or rename those by hand. Stamping them with today would file real work under a
  day it was not done on.
- **A name opening with something date-shaped that is not a date** — `2026-13-45-foo.md`. It is
  neither dated nor plainly undated, and this version will not decide which. Name the files and ask
  for a real close date or a bare slug. This is the stop-rather-than-skip case: treating such a name
  as already-dated would record the repo conformant on a name no reader can order, and treating it
  as undated would prefix a second date onto it.

Afterwards:

- **Whether each date is the right one.** The rename asserts that a name opens with a real date and
  that the bytes survived; it cannot know whether the commit that added a file to `done/` is the
  moment the work was actually finished. A memo closed in one session and committed a week later
  carries the commit's date, and only a person can say that matters.
- **A memo whose own slug begins with a date.** A title like "2026 09 15 was the day the job
  stopped" derives a slug opening with `2026-09-15-`, which reads as already dated and is left
  alone. It is rare and harmless — the name still sorts — but the date is the title's, not the
  close's.
- **Other repos.** This settles one repo; `/github-status` reports which clones are still behind.

## When it does not apply

- **`.claude/memos/done/` holds no memo at all.** Positive evidence, not absence: count the open
  backlog and report it alongside, so the reading says a backlog was read and had nothing addressed
  in it yet. A repo that keeps no memos reports the same way, naming the missing directory. Either
  way there is no name here to carry a date, and the next close writes the new shape unaided.
- **Every memo in `done/` already opens with a real date.** The whole directory was read and each
  name checked, parsing the run as a real date rather than merely matching the shape.

## Continuing rule

None — this is a one-time migration.
