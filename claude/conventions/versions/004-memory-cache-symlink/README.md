---
title: Memory cache points into the repo
scope: machine
---

## What changed

Claude Code writes project memory to a machine-local cache directory named after the repo's path.
Nothing version-controls it, so what one machine learned about a project is invisible from the other
and gone the day the cache is cleared. The convention redirects that directory, by a link, at a
committed `.claude/memory/` inside the repo: the harness keeps reading and writing the same path,
the files live in git, and a clone carries them. The `link-project-memory.sh` script in
`claude/scripts/` is what makes the link and has done since before this version existed; what is new
here is the preconditions and the assertions around it.

Machine-scoped, so adopting it writes both records: the committed one says this repo decided the
convention, and the gitignored `.claude/conventions.local` says this machine actually made the link.
A fresh clone holds the first without the second and reads as decided but not wired here, which is
true — the link is per-machine and nothing in the repo can carry it.

It hands the checker nothing. A link that later breaks is what `check-install.py` reports at session
start, and a rule re-asserting it on every commit would be measuring the machine rather than the
repo.

## Migrating an existing repo

There is work here when the repo commits a `.claude/memory/` directory and this machine's cache for
the repo is either a plain directory or absent. Absent is the commoner half: a repo the harness has
never opened here has no cache at all, and the link has simply never existed.

Run `~/.claude/scripts/link-project-memory.sh` in the repo. It moves anything the plain cache holds
into `.claude/memory/`, replaces the cache with a link to it, and writes a `.gitkeep` where the
directory would otherwise be empty so a fresh clone still has somewhere to link to.

Check the result with `os.path.samefile` on the two paths, which reads `st_dev` and `st_ino`, rather
than with a path string. On Git Bash `ln -s` silently makes a copy, and a copy resolves to itself, so
`realpath` returns a perfectly sensible path and `isdir` calls it healthy while it mirrors nothing —
different inodes is the only signal (`learnings/comparing-paths-symlinks-and-case.md`). The same
comparison covers the Windows directory junction the script creates there, which `os.path.islink`
has answered False for since Python 3.8; keying the check on that would report every correctly wired
repo on that machine as broken.

Four states are a question for the user rather than work to do:

- **The cache is already a link pointing somewhere other than this repo.** Where it should point, and
  what becomes of the memory it holds, is not this version's guess. Remove or repoint it by hand and
  start again.
- **The plain cache directory and the repo copy hold the same filename.** Those are two versions of
  one memory, and which survives is a human's call. Name each colliding pair; every other file in the
  cache is carried across without asking.
- **Something that is not a directory sits at either end** — a file where the cache directory
  belongs, or a `.claude/memory` that is a file rather than a directory. Move neither aside.
- **The cache holds this repo under a different spelling of its path.** Both `~/projects` and
  `~/Projects` open one directory on a filesystem that folds case, and the harness names the cache
  after the spelling the session was started from — so one repo can own two cache directories, and
  this machine has a real example. Wiring the one the harness is not reading would leave the machine
  looking wired while every session still wrote outside the repo, so name the variant and let the
  user choose.

A git that will not say which directory is the repository root stops the work rather than becoming a
question. The cache directory is named after exactly that path, so a wrong answer does not produce a
wrong record — it produces a link the harness never reads, which is the one failure this version
exists to catch.

Afterwards:

- Commit `.claude/memory/`. The link makes the harness write into the repo; it stages nothing, and
  memory written after the link is made sits there untracked until a commit picks it up. The
  `.gitkeep` shows up untracked beside the rest — the one repo file this machine-scoped migration
  adds.
- Run the same migration on the other machine. The committed record travels and the link does not, so
  the other machine reads this as decided and unwired until it does the work itself.
- Check `git check-ignore -v .claude/memory/`. A repo excluding `.claude/` wholesale leaves every
  memory file untracked, which puts the files in the repo and out of git — the same halfway state the
  un-versioned cache was.
- Read what was carried out of the un-versioned cache. Those files were written by sessions that ran
  before the link existed; they are real project memory, and several are usually worth a line in
  `MEMORY.md` while the context is still there.

## When it does not apply

There is no `.claude/memory/` in the repo. That is positive evidence read off the repo rather than an
absence inferred from this machine: the convention points the cache at a committed directory, and
with no such directory there is nothing to point at. Never create one, because an empty memory
directory is cruft and whether a repo keeps project memory at all is not a machine's business.

The machine is already wired is the other half: the cache and the repo copy are one directory under
`samefile`, and nothing needs touching.

The two states this version distinguishes differ in what has been done to the machine, never in what
the repo holds — the same tree is conformant on one machine and not on another.

## Continuing rule

None — this is a one-time migration.
