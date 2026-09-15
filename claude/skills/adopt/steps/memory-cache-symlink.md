---
version: 4
slug: memory-cache-symlink
title: Memory cache points into the repo
scope: machine
---

# Memory cache points into the repo

Claude Code writes project memory to a machine-local cache directory named after the repo's
path. Nothing version-controls it, so what one machine learned about a project is invisible from
the other and gone the day the cache is cleared. The convention redirects that directory, by a
link, at a committed `.claude/memory/` inside the repo: the harness keeps reading and writing
the same path, the files live in git, and a clone carries them. The `link-project-memory.sh`
script in `claude/scripts/` is what makes the link and has done since before this step existed;
this step is that script with the preconditions and the assertions `/adopt` owes around it.

Machine-scoped, so an `applied` line goes into both record files: the committed one says this
repo decided the convention, and the gitignored `.claude/conventions.local.tsv` says this
machine actually made the link. A fresh clone holds the first without the second and reads as
decided but not wired here, which is true — the link is per-machine and nothing in the repo can
carry it.

## Applies when

The repo commits a `.claude/memory/` directory, and this machine's cache for the repo is either
a plain directory or absent. Absent is the commoner half: a repo the harness has never opened
here has no cache at all, and the link has simply never existed.

## Does not apply when

There is no `.claude/memory/` in the repo. That is positive evidence read off the repo rather
than an absence inferred from this machine: the convention points the cache at a committed
directory, and with no such directory there is nothing to point at. This step never creates one,
because an empty memory directory is cruft and whether a repo keeps project memory at all is not
a machine's business. It records `n/a`, which goes only to the committed record — true on every
machine, so neither machine asks again.

A machine already wired is the other half, and verify sees it first: the cache and the repo copy
are one directory, the repo is recorded as in the target shape, and nothing is touched. Probe
repeats the same reading for anyone who runs it directly.

## Cannot tell

- **The cache is already a link pointing somewhere other than this repo.** Where it should
  point, and what becomes of the memory it holds, is not this step's guess. Remove or repoint it
  by hand and re-run.
- **The plain cache directory and the repo copy hold the same filename.** Those are two versions
  of one memory, and which survives is a human's call. The question names each colliding pair.
  Every other file in the cache is carried across by the script rather than asked about.
- **Something that is not a directory sits at either end** — a file where the cache directory
  belongs, or a `.claude/memory` that is a file rather than a directory. This step moves neither
  aside.
- **The cache holds this repo under a different spelling of its path.** Both `~/projects` and
  `~/Projects` open one directory on a filesystem that folds case, and the harness names the
  cache after the spelling the session was started from — so one repo can own two cache
  directories, and this machine has a real example. Wiring the one the harness is not reading
  would leave the machine looking wired while every session still wrote outside the repo, so the
  variant is named and the choice is the user's.

A git that will not say which directory is the repository root is exit 3 in all three commands
rather than a question. The cache directory is named after exactly that path, so a wrong answer
does not produce a wrong record — it produces a link the harness never reads, which is the one
failure this step exists to catch.

## Verify

The question is whether this machine's cache for the repo *is* the repo's own `.claude/memory/`,
not whether a script was ever run here. Both paths are resolved and compared with
`os.path.samefile`, which reads `st_dev` and `st_ino`.

A path string cannot answer it. On Git Bash `ln -s` silently makes a copy, and a copy resolves
to itself, so `realpath` returns a perfectly sensible path and `isdir` calls it healthy while it
mirrors nothing — different inodes is the only signal
(`learnings/comparing-paths-symlinks-and-case.md`). The same comparison covers the Windows
directory junction the script creates there, which `os.path.islink` has answered False for since
Python 3.8; keying the assertion on that would report every correctly wired repo on that machine
as broken.

It cannot pass vacuously. A repo with no cache fails, a cache that is a plain directory fails, a
cache that is a copy of the repo's memory fails, and a dangling link fails — each with the
sentence saying which. Exit 2 is reserved for the one thing the check has no subject for: a repo
committing no `.claude/memory/`, where the shape being asserted has no counterpart to compare
against, and `/adopt` goes on to probe and records `n/a`.

The two states this step distinguishes differ in what has been done to the machine, never in
what the repo holds — the same tree is conformant on one machine and not on another, and the
assertion is `samefile` against a cache path derived from wherever the repo sits.

## By hand, after the script

- Commit `.claude/memory/`. The link makes the harness write into the repo; it does not stage
  anything, and memory written after the link is made sits there untracked until a commit picks
  it up. An empty directory also gains a `.gitkeep`, written by `link-project-memory.sh` so a
  fresh clone still has somewhere to link to — the one repo file this machine-scoped step adds,
  and it shows up untracked beside the rest.
- Re-run the step on the other machine. The committed record travels and the link does not, so
  the other machine reads this as decided and unwired until it runs `/adopt` itself.
- Check `git check-ignore -v .claude/memory/`. A repo excluding `.claude/` wholesale leaves
  every memory file untracked, which puts the files in the repo and out of git — the same
  halfway state the un-versioned cache was.
- Read what the run carried out of the un-versioned cache. Those files were written by sessions
  that ran before the link existed; they are real project memory, and several are usually worth
  a line in `MEMORY.md` while the context is still there.
