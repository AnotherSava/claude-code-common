# Two strings that name the same file, and compare unequal

Path equality looks like string equality and is not. Two producers hand you two spellings of one
file, `==` says no, and nothing raises — the file is simply dropped from whatever set you were
building. Measured 2026-09-12 while writing a check that had to decide whether a path this session
wrote lay inside the repo being committed.

## `realpath` resolves symlinks; it does not canonicalise case

`os.path.realpath` (and `readlink -f`) substitutes the symlink's **stored target string**. If that
string spells a directory differently from the way it sits on disk, the result inherits the
symlink's spelling, and a case-insensitive filesystem keeps both working so nothing ever complains:

```
$ readlink ~/.claude/learnings
/Users/me/projects/dotfiles/claude/learnings     # lowercase p, as stored

$ git -C ~/.claude/learnings rev-parse --show-toplevel
/Users/me/Projects/dotfiles                      # capital P, as on disk
```

So a file edited through the symlink realpaths to `/Users/me/projects/…` while every path git
reports begins `/Users/me/Projects/…`. Both open the same bytes. Neither `==` nor `in a_set`
agrees. The observed failure: a file written through `~/.claude/skills/` was checked for membership
in a set built from `git status` output and came back `False`, so the one case the check existed for
was the one it could not see.

## What does not fix it

- **`os.path.normcase`** is a no-op everywhere except Windows, where it lowercases. On macOS it
  returns the string unchanged, so it reads like a canonicaliser and does nothing.
- **`os.path.abspath` / `normpath`** are textual. They never touch case and never resolve a link.
- **`os.path.samefile`** is genuinely correct — it compares `st_dev`/`st_ino` — but it needs both
  paths to exist. A deleted-but-uncommitted file, which is exactly what `git status` reports as
  ` D`, raises `FileNotFoundError`.

## What does

**Make both sides come from the same producer.** The comparison that worked was between two
`git rev-parse --show-toplevel` results, because git normalises to the on-disk spelling whichever
path you hand it — so asking git about the symlinked path and about the real one yields the same
string. Prefer routing both operands through one authority over fixing up the strings afterwards.

Where one side is fixed and the other is not, re-spell it onto the authoritative root. Strip the
prefix case-insensitively and re-join, trying both the authority's spelling and the realpath's:

```python
def rebase(path: str, root: str) -> str:
    """Re-spell `path` under the given spelling of `root`."""
    for base in (root, os.path.realpath(root)):
        prefix = base.rstrip(os.sep) + os.sep
        if path.casefold().startswith(prefix.casefold()):
            return os.path.join(root, path[len(prefix):])
    return path
```

`casefold()` rather than `lower()`; it is the comparison-grade fold, and it costs nothing here.
This is safe on a case-insensitive volume by definition. On a case-sensitive one it can in
principle join two files differing only in case — a shape that cannot occur on the volume where the
problem exists in the first place.

## The general rule

Treat a path string as belonging to its producer. `git`, `realpath`, a symlink target, an editor's
`file_path` argument, and `os.getcwd()` are five different producers, and any two of them can
disagree about case, about symlink resolution, or about a trailing slash while naming one file.
Before comparing paths from two sources, normalise through one of them — and when a membership test
silently comes back empty, suspect the spelling before suspecting the data.
