---
version: 5
slug: memory-file-shape
title: Memory files carry frontmatter and bare links
scope: repo
---

# Memory files carry frontmatter and bare links

Project memory is a directory of markdown files with a `MEMORY.md` index beside them. Two
things make that readable by anyone other than whoever wrote it: each file opens with a
`---` block saying what the memory is, and each index entry links to its file by bare
filename. The same memories are described by a second index, the Global Memory list in
`CLAUDE.md`, which sits in a different directory and so writes the same file as
`~/.claude/memory/<file>.md`. Markdown never expands `~`, so a line copied from one index
into the other is a link that resolves to nothing — and the two lists look interchangeable,
which is exactly why they are not.

Every repo holding a memory directory was already in this shape when the step was written:
no file missing its block, no index entry naming a path. So this is a baseline step and it
has no work to do today. What it buys is that "current" stops meaning "nobody looked", and
that `audit` re-runs `verify` in every repo that recorded a line — so the first repo to
drift is a finding rather than a silence.

## Applies when

The index holds at least one link target that is not a bare filename — `./x.md`,
`~/.claude/memory/x.md`, `memory/x.md` — and a file of that name sits beside the index, so
the rewrite copies a name off the directory rather than guessing one. Every memory file
already opens with `---`, because the script rewrites the index and nothing else.

## Does not apply when

There is no `.claude/memory/` directory, or there is one and it holds no memory file. Both
are read off the directory itself rather than inferred from something that is not there: no
project memory has been saved in this repo, there is nothing whose shape this convention
governs, and the step never creates any. An empty directory is the normal state of a repo
whose memory cache was wired before anything was written to it.

Already in the target shape is the other case, and it was every repo in the fleet when this
step was written:
every file opens with `---`, and every index link names a file sitting beside it. Verify
sees that first and records the repo without touching anything; probe repeats the same
reading for a direct run, and for `audit` re-deriving an `n/a` line.

## Cannot tell

- **A memory file that does not open with `---`.** What type of memory it is and when it
  was saved are written nowhere in the text, and this step will not invent either, so no
  amount of rewriting reaches the target shape from here. Add the block by hand and re-run.
  A file that reads as base64 rather than prose is a transcrypt repo nobody has unlocked
  rather than a missing block; unlock it first.
- **Memory files with no `MEMORY.md` beside them.** Writing the index means summarising each
  memory in a line, which is a sentence a human writes.
- **A path-shaped target naming no file beside the index** — an entry pointing at a document
  elsewhere in the repo, or at a file since renamed. Rewriting it to a bare filename would
  point the entry at something that is not there. The same goes for a bare target that names
  no such file: whether it was renamed or deleted is not this step's guess.
- **A `](` the parser cannot read as a link.** It is printed verbatim with its line number
  and nothing is written, because a target this reader cannot classify is plausibly a
  path-shaped one, and walking past it would report an index asserted bare while one entry
  never was.
- **A file under the directory that cannot be read as text at all.** The shape is
  unobservable rather than wrong, and the difference matters: the first is a question, the
  second a failure.

## Fetch before running

Apply rewrites `MEMORY.md`, a committed file the other machine may have appended an entry
to, and an append merges cleanly against a rewrite only when both sides start from the same
text — `learnings/git-stash-pull-safety.md`. The `/adopt` procedure refuses to start on a
branch behind its upstream, which is the gate that matters here.

Afterwards, `git diff` on the index should show link targets changing and nothing else: the
rewrite replaces the bytes between `](` and `)` and copies every other byte through, line
endings included. Any blurb that moved is a defect in this step, not a tidy-up.

## Verify

The target shape, re-derived from disk: every `.md` under `.claude/memory/` other than the
index opens with `---`; a `MEMORY.md` sits beside them; and every markdown link target in it
is a bare filename that names a file in that same directory. A target carrying a real URL
scheme — an `https://` reference in a blurb, a `mailto:` — names nothing in the directory
and is read as the outward reference it is; a `file:` target is a machine-specific absolute
path, which committed documentation may not carry, so it fails like any other path.

It cannot pass vacuously. A directory holding no memory file is exit 2, not a pass, and a
single file missing its block fails the whole check rather than being counted against the
files that have one.

Exit 2 is reserved for a shape that genuinely cannot be observed: no directory to read, or a
file in it that will not decode as text.

## By hand, after the script

- Read the index entries the run rewrote. The script asserts that the link resolves, never
  that the sentence beside it still describes the memory it points at.
- Read the frontmatter of anything recently added. The script asserts only that the block
  opens the file; whether `name`, `description` and `type` say what the memory actually
  holds is not something it can read.
- Check for a memory file no index entry names. The reverse direction is deliberately
  outside verify: a file left out on purpose and one forgotten look identical from here, and
  a file nothing links to is invisible to anyone reading the index.
- If an entry was copied from the Global Memory list in `CLAUDE.md`, check the blurb as well
  as the link — that list describes files under `~/.claude/memory/`, which are different
  memories from this repo's, and a copied line usually carries a claim about the wrong one.
