# Asking git which repo a check is running in

A check that judges "this repo" against a record keyed by repo name has to decide what the repo is called, and the obvious answer — the basename of the path it was handed — is wrong in three ways that all occur in ordinary use. Each one is silent, and two of them fail in both directions at once: a fabricated finding appears while the genuine one disappears, at the same count and the same exit status, so neither tells the reader anything is off.

This is the identity question only. Which *files* that same check should then read is a separate defect with its own failures, in `git-checking-what-a-commit-will-contain.md` — both were found in `ports-from-registry`, and fixing one leaves the other.

The three positions a caller can be in, and what each wants:

- **A linked worktree.** `git worktree add` gives a checkout whose basename is whatever the caller chose — a forked sub-skill creates one per run, named after itself. The *content* under review is this worktree's, and the *identity* is the main worktree's.
- **A subdirectory.** A path inside the repo is not a repo. Both the identity and the scan root belong to the checkout containing it, because a rule reading only the subtree misses whatever sits above it.
- **A clone in a differently named directory.** Nothing on the filesystem recovers the intended name, but the origin remote does: one repo cloned as `tripit` on one machine and `trips` on the other (its GitHub name) is the same repo, and a record keyed on folders judged one of the clones as another project. Measured 2026-10-20, when the Windows clone failed `ports-from-registry` and the macOS one passed.

## The two questions take different commands

```bash
git -C "$path" worktree list --porcelain | head -1   # "worktree <main worktree root>"
git -C "$path" rev-parse --show-toplevel             # the checkout $path is in
```

The first names the **main** worktree from any position inside the repo, a bare repo included, and is what an identity should come from. The second names the **containing** checkout — in a linked worktree that is the linked root, which is correct, since its content is the subject. A check needing both must call both; using either for both reintroduces one of the failures.

Measured 2026-10-06 across 18 repos: the two agree for every ordinary checkout, so adopting them changes no verdict on a tree nobody has branched. In a scratch linked worktree they diverge exactly as intended, and from a subdirectory the first still answers the repo while a basename answers the directory.

`--show-toplevel` is not a substitute for the first: in a linked worktree it returns that worktree's own root, which is the whole reason both exist.

## What the alternatives cost, measured rather than reasoned

- **The origin remote is the identity, but only together with the record it keys.** The GitHub repository name, parsed from `git remote get-url origin`, is the one name every clone agrees on, so the ports registry's `owner` is that name. Switching the reader alone is not enough: measured 2026-10-06, the origin name disagreed with the directory name for 4 of 18 repos, and a record written against directory names lost the owner of 19 of 34 entries. The switch on 2026-10-20 renamed the record's owners in the same change, and every launch script that passes an owner with them, since `allocate` refuses an owner that differs from the recorded claim. Without a GitHub origin, fall back to the main worktree's directory name below.
- **`git rev-parse --git-common-dir`** names the main worktree correctly for an ordinary checkout and for a linked one, and fails for `git init --separate-git-dir`, where it points at the external git directory whose parent is unrelated to the work tree. The `worktree list` form is right in that case too, which is why it is the one above.
- **A symlinked path does not misfire at all**, provided the code resolves the path before taking a basename. That resolution is also what makes the symlink case invisible, so do not count it as evidence the basename approach works.

## Limits to state rather than close

Only a repo with no GitHub origin still answers from the directory name, and there the old limits stand: a clone in a differently named directory, and `--separate-git-dir`. A record can also name a project that is not a git repository at all, which no git-derived identity reaches.

**Renaming the GitHub repository is now the silent breakage** that renaming a folder used to be. Whatever renames the repo has to rename the record's owners in the same change; otherwise the next run of the check reports every exempted literal as belonging to some other project.

## Matching a multi-owner field

Where a record's owner field can name several projects, match whole tokens rather than a substring. `name in owner_string` let a repo called `travel` match an entry owned by `travel-map`, which granted it that entry's exemption — reproduced end to end on 2026-10-06. Splitting on the separator and comparing elements keeps the genuine multi-owner case working and removes the accidental prefix match:

```python
name in {part.strip() for part in str(claim.get("owner", "")).split(",")}
```
