---
version: 14
slug: memos-done-dated
title: Addressed memos carry their close date at the front of the name
scope: repo
script: memos-done-dated.py
---

An addressed memo is never deleted — the command that used to clear `.claude/memos/done/` is gone,
because the record of what was decided is the cheapest thing in a repo to keep and the only part of a
backlog that cannot be rebuilt. That makes `done/` append-only, and nothing in the memo skill lists
it: `list` and `show` both resolve against the open backlog. Its readers are therefore a file browser,
`ls` and `git status`, and a name is the only thing any of those sorts by.

So the close date goes into the name, which is the one place the backlog inverts its own rule that a
sort key lives in metadata rather than in an identifier. The trade is stated rather than hidden: a
second ordering over done memos would cost a rename of them all, and that is accepted here because
there is no reader to give a field to. Repos adopted before this hold done memos named by slug alone,
which sort alphabetically and say nothing about when anything was decided.

## Applies when

`.claude/memos/done/` holds at least one `.md` file whose name does not open with a real
`YYYY-MM-DD-` prefix, and git can say when each of those was closed — the date the commit that added
the file at its `done/` path was authored.

## Does not apply when

- **`.claude/memos/done/` holds no memo at all.** Positive evidence, not absence: the open backlog is
  counted and reported alongside, so the line says a backlog was read and had nothing addressed in it
  yet. A repo that keeps no memos reports the same way, naming the missing directory. Either way
  there is no name here to carry a date, and the next close writes the new shape unaided.
- **Every memo in `done/` already opens with a real date.** The whole directory was read and each name
  checked, which is the shape `verify` passes on.

## Cannot tell

- **A done memo git has never seen.** Its close date is unreadable, because the only honest source is
  the commit that put it in `done/` — an mtime is rewritten by a clone, a checkout or a rebase and
  answers when this machine last wrote the file. The question, printed with the names: commit the
  close first and re-run, or rename those by hand. Stamping them with today would file real work under
  a day it was not done on.
- **A name opening with something date-shaped that is not a date** — `2026-13-45-foo.md`. It is
  neither dated nor plainly undated, and this step will not decide which. The question names the files
  and asks for a real close date or a bare slug. This is the abort-rather-than-skip case: treating
  such a name as already-dated would record the repo conformant on a name no reader can order, and
  treating it as undated would prefix a second date onto it.

## Verify

Every `.md` file in `.claude/memos/done/` opens with `YYYY-MM-DD-`, and that run parses as a real date
rather than merely matching the shape. Asserted per file off disk, listed one line each, so a single
undated name fails the whole repo.

It is not vacuous: a `done/` that is empty or absent exits 2, not 0 — "every done memo is dated" is
true of a repo that has closed none, and recording `applied` there would claim a migration in a
directory the step never read. The `before/` fixture is the proof in the other direction, holding two
undated memos that `verify` must fail on before anything has run.

## By hand, after the script

- **Whether each date is the right one.** The step asserts that a name opens with a real date and that
  the bytes survived the rename; it cannot know whether the commit that added a file to `done/` is the
  moment the work was actually finished. A memo closed in one session and committed a week later
  carries the commit's date, and only a person can say that matters.
- **A memo whose own slug begins with a date.** A title like "2026 09 15 was the day the job stopped"
  derives a slug opening with `2026-09-15-`, which this step reads as already dated and leaves alone.
  It is rare and harmless — the name still sorts — but the date is the title's, not the close's.
- **Other repos.** This records one repo. `/github-status` reports which clones are still behind.
