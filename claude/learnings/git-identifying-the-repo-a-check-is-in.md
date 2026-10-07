# Asking git which repo a check is running in

A check that judges "this repo" against a record keyed by repo name has to decide what the repo is called, and the obvious answer — the basename of the path it was handed — is wrong in three ways that all occur in ordinary use. Each one is silent, and two of them fail in both directions at once: a fabricated finding appears while the genuine one disappears, at the same count and the same exit status, so neither tells the reader anything is off.

This is the identity question only. Which *files* that same check should then read is a separate defect with its own failures, in `git-checking-what-a-commit-will-contain.md` — both were found in `ports-from-registry`, and fixing one leaves the other.

The three positions a caller can be in, and what each wants:

- **A linked worktree.** `git worktree add` gives a checkout whose basename is whatever the caller chose — a forked sub-skill creates one per run, named after itself. The *content* under review is this worktree's, and the *identity* is the main worktree's.
- **A subdirectory.** A path inside the repo is not a repo. Both the identity and the scan root belong to the checkout containing it, because a rule reading only the subtree misses whatever sits above it.
- **A clone in a renamed directory.** Nothing recovers the intended name from the filesystem here, so this is the case to state as a limit rather than solve.

## The two questions take different commands

```bash
git -C "$path" worktree list --porcelain | head -1   # "worktree <main worktree root>"
git -C "$path" rev-parse --show-toplevel             # the checkout $path is in
```

The first names the **main** worktree from any position inside the repo, a bare repo included, and is what an identity should come from. The second names the **containing** checkout — in a linked worktree that is the linked root, which is correct, since its content is the subject. A check needing both must call both; using either for both reintroduces one of the failures.

Measured 2026-10-06 across 18 repos: the two agree for every ordinary checkout, so adopting them changes no verdict on a tree nobody has branched. In a scratch linked worktree they diverge exactly as intended, and from a subdirectory the first still answers the repo while a basename answers the directory.

`--show-toplevel` is not a substitute for the first: in a linked worktree it returns that worktree's own root, which is the whole reason both exist.

## What the alternatives cost, measured rather than reasoned

- **The origin remote is not an identity** wherever the record keys on anything else. Parsing the repo name out of `git remote get-url origin` disagreed with the directory name for 4 of 18 repos — and the record those names index was written against directory names, so switching lost the owner of **19 of 34** entries. A repo whose folder has been renamed to match its remote is the one case where this is the right answer, and it is the case the rename is meant to create rather than one to assume.
- **`git rev-parse --git-common-dir`** names the main worktree correctly for an ordinary checkout and for a linked one, and fails for `git init --separate-git-dir`, where it points at the external git directory whose parent is unrelated to the work tree. The `worktree list` form is right in that case too, which is why it is the one above.
- **A symlinked path does not misfire at all**, provided the code resolves the path before taking a basename. That resolution is also what makes the symlink case invisible, so do not count it as evidence the basename approach works.

## Limits to state rather than close

Two shapes still answer from the directory name, and a docstring should say so instead of implying the problem is solved: a clone sitting in a directory named differently from its recorded name, and `--separate-git-dir`. A third is outside git entirely — a record can name a project that is not a git repository at all, and no git-derived identity reaches it.

**A record keyed by directory name turns a folder rename into a silent breakage**, which is the other half of this. Whatever renames the folder has to rename the record in the same change; otherwise the next run of the check reports every exempted literal as belonging to some other project. Put that step in whatever skill or script performs the rename, not in a note beside the record.

## Matching a multi-owner field

Where a record's owner field can name several projects, match whole tokens rather than a substring. `name in owner_string` let a repo called `travel` match an entry owned by `travel-map`, which granted it that entry's exemption — reproduced end to end on 2026-10-06. Splitting on the separator and comparing elements keeps the genuine multi-owner case working and removes the accidental prefix match:

```python
name in {part.strip() for part in str(claim.get("owner", "")).split(",")}
```
