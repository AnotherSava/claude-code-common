---
title: Memory files carry frontmatter and bare links
rules: memory-file-shape
---

## What changed

Project memory is a directory of markdown files with a `MEMORY.md` index beside them. Two things
make that readable by anyone other than whoever wrote it: each file opens with a `---` block saying
what the memory is, and each index entry links to its file by bare filename. The same memories are
described by a second index, the Global Memory list in `CLAUDE.md`, which sits in a different
directory and so writes the same file as `~/.claude/memory/<file>.md`. Markdown never expands `~`,
so a line copied from one index into the other is a link that resolves to nothing — and the two
lists look interchangeable, which is exactly why they are not.

Every repo holding a memory directory was already in this shape when this version was written: no
file missing its block, no index entry naming a path. So this is a baseline version with no work to
do that day. What it buys is that "current" stops meaning "nobody looked", and that the rule it
hands the checker runs on every commit in every repo that adopted it — so the first repo to drift is
a finding rather than a silence.

## Migrating an existing repo

There is work here when the index holds at least one link target that is not a bare filename —
`./x.md`, `~/.claude/memory/x.md`, `memory/x.md` — and a file of that name sits beside the index, so
the rewrite copies a name off the directory rather than guessing one.

Fetch first, and do not run this on a branch behind its upstream: the rewrite touches `MEMORY.md`, a
committed file the other machine may have appended an entry to, and an append merges cleanly against
a rewrite only when both sides start from the same text — `learnings/git-stash-pull-safety.md`.

Rewrite only the bytes between `](` and `)`, copying every other byte through, line endings
included. Afterwards `git diff` on the index should show link targets changing and nothing else; any
blurb that moved is a defect in the rewrite rather than a tidy-up, so restore it. Nothing else in
the directory is touched — every memory file already opens with `---` wherever this migration has
work to do.

Five states are a question for the user rather than work to do:

- **A memory file that does not open with `---`.** What type of memory it is and when it was saved
  are written nowhere in the text, and this version will not invent either, so no amount of
  rewriting reaches the target shape from here. Ask for the block and start again. A file that reads
  as base64 rather than prose is a transcrypt repo nobody has unlocked rather than a missing block;
  unlock it first.
- **Memory files with no `MEMORY.md` beside them.** Writing the index means summarising each memory
  in a line, which is a sentence a human writes.
- **A path-shaped target naming no file beside the index** — an entry pointing at a document
  elsewhere in the repo, or at a file since renamed. Rewriting it to a bare filename would point the
  entry at something that is not there. The same goes for a bare target that names no such file:
  whether it was renamed or deleted is not this version's guess.
- **A `](` that will not read as a link.** Print it verbatim with its line number and write nothing,
  because a target nobody could classify is plausibly a path-shaped one, and walking past it would
  report an index asserted bare while one entry never was.
- **A file under the directory that will not read as text at all.** The shape is unobservable rather
  than wrong, and the difference matters: the first is a question, the second a failure.

Afterwards:

- Read the index entries that were rewritten. The rewrite makes the link resolve; it says nothing
  about whether the sentence beside it still describes the memory it points at.
- Read the frontmatter of anything recently added. The block opening the file is all that is
  asserted; whether `name`, `description` and `type` say what the memory actually holds is not
  something any check can read.
- Check for a memory file no index entry names. The reverse direction is deliberately outside the
  rule: a file left out on purpose and one forgotten look identical from here, and a file nothing
  links to is invisible to anyone reading the index.
- If an entry was copied from the Global Memory list in `CLAUDE.md`, check the blurb as well as the
  link — that list describes files under `~/.claude/memory/`, which are different memories from this
  repo's, and a copied line usually carries a claim about the wrong one.

## When it does not apply

There is no `.claude/memory/` directory, or there is one and it holds no memory file. Both are read
off the directory itself rather than inferred from something that is not there: no project memory
has been saved in this repo, there is nothing whose shape this convention governs, and it creates
none. An empty directory is the normal state of a repo whose memory cache was wired before anything
was written to it.

Already in the target shape is the other case, and it was every repo in the fleet when this version
was written: every file opens with `---`, and every index link names a file sitting beside it.

## Continuing rule

`memory-file-shape` — every `.md` under `.claude/memory/` other than the index opens with `---`, a
`MEMORY.md` sits beside them, and every markdown link target in it is a bare filename naming a file
in that same directory. A target carrying a real URL scheme is read as the outward reference it is;
a `file:` target is a machine-specific absolute path, which committed documentation may not carry,
so it fails like any other path.
