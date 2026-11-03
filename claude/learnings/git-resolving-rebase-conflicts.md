# Resolving conflicts in the middle of a rebase

Two things behave differently while `git rebase` is stopped on a conflict, and both fail quietly.

## `@{upstream}` stops resolving

A stopped rebase leaves HEAD detached, so `@{upstream}` (and `@{u}`) has no branch to read from:

```
$ git show @{upstream}:scripts/README.md
fatal: HEAD does not point to a branch
```

Redirected into a file, that failure leaves the file empty, since the shell creates it before git runs. A script that then reads the file
and appends to it writes a truncated result, which commits cleanly. Measured 2026-11-03: a merged
README came out holding only the appended section, and only a re-read before `rebase --continue`
caught it. Name the ref outright for the whole rebase (`upstream/master`, `origin/main`), and make any
script that edits a file it read check what it read (`assert s.startswith(...)`) before writing back.

## `--ours` and `--theirs` are swapped

A rebase replays your commits onto the target, so during it:

- `--ours` is the branch being rebased **onto**: upstream's version.
- `--theirs` is the commit being replayed: your local version.

`git checkout --ours -- <path>` therefore takes upstream's copy, which is what you want when the local
commit's change to that file has become redundant. In a merge the two words mean the opposite.

## Two sides adding the same mechanism

If upstream independently builds what a local commit added (the same directory, script hook or cache
key), the conflict is `AA` (both added) on the shared files. Take upstream's copy of everything the two
sides share. Then reduce the local commit to what upstream lacks, renamed or renumbered to fit
upstream's layout, instead of hand-merging two implementations of the same thing.
