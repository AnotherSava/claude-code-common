---
created: 2026-09-15 14:39:36
platform: windows
---

# Write the missing v4 conventions.local.tsv line on the Windows box

Measured 2026-09-15 on the Windows box, during `/adopt` in this repo.

`conventions.py status` prints this on every run, and will keep printing it:

    v4   memory-cache-symlink         machine  decided in this repo, not wired on this machine

## It is a record gap, not a wiring gap

The wiring is genuinely in place. `os.path.samefile` between this machine cache directory and the repo `.claude/memory/` returns **True**. What is missing is only `.claude/conventions.local.tsv`, which does not exist here at all.

(`os.path.islink` returns False on that same path, because the cache is a Windows junction rather than a symlink. That is a red herring and is now written up in `learnings/git-bash-windows-symlinks.md`; `samefile` is the honest instrument and the v4 step already uses it.)

## How it probably got this way

The committed `.claude/conventions.tsv` carries `4 memory-cache-symlink applied 2026-09-15`, so the repo has decided it. `conventions.py record` writes an `applied` machine-scope line into **both** files — the committed one and the gitignored local one — so a line in the first with nothing in the second points at the v4 walk having run on the other box and been pulled here, never on this one.

## The fix, one step

Run the step verify here, and on exit 0 record it:

    python claude/skills/adopt/steps/memory-cache-symlink.py verify .
    python claude/skills/adopt/conventions.py record . 4 applied "<that verify last line, verbatim>"

`record` re-runs the verify itself before writing, so the first command is there to read the note off. It writes the local file and rewrites the committed line identically; nothing else changes, and the status notice stops.

## Why it needs this box

`.claude/conventions.local.tsv` is gitignored and per-machine by design — it says *this machine wired it*. It can only be written where it is missing, which is here.
