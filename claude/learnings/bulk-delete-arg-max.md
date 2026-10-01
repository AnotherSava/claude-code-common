# Deleting a tree by naming its files, and where that stops working

Naming the files you are about to delete is the only review a delete gets: the list is on screen, and a
path that is wrong announces itself. Passing that list to one `rm` keeps the review without the blindness
of `rm -rf`. It works up to a hard ceiling, and the way it fails past the ceiling is the reason to know
where the ceiling is.

Measured 2026-10-01 on macOS, two generated trees of 100 files per directory, timed from outside:

| tree | `rm -rf <dir>` | `find` the list, then one `rm` | list size |
|---|---|---|---|
| 1,000 files | 0.062s | 0.097s | 72,019 bytes |
| 20,000 files | 0.844s | **refused** | 1,467,599 bytes |

`getconf ARG_MAX` was 1,048,576. At ordinary path lengths the list runs about 72 bytes per file, so the
ceiling arrives near **14,500 files** — well under the size of a `node_modules` or a build tree.

**Performance is not the objection.** The `find` traversal plus the longer command line cost 35 ms at
1,000 files. Anyone rejecting the named-list form on speed is optimising the wrong thing.

**The failure past the ceiling is partial, not clean.** `rm` refuses the whole invocation with
`argument list too long`, so nothing is deleted — and a directory sweep written to follow it then fails
on every directory in turn:

```
rm: argument list too long
rmdir: .../d149/nested: Directory not empty
rmdir: .../d149: Directory not empty
      ... once per directory
```

The tree is left standing and the terminal carries one error line per directory, which buries the one
line that explains why. A delete that half-succeeds is worse than one that never started, and that is
what makes the ceiling worth respecting rather than discovering.

So the named-list form belongs exactly where its review is real — a set small enough to read — and a set
too large to read is the signal to stop and ask rather than to reach for `-rf`. Deciding *whether* a path
may be deleted without asking is a separate question, answered by whether git already calls it
disposable; `gitignore-anchoring-and-scope.md` has the semantics of that check, including the two ways it
answers the opposite of what a caller expects.
