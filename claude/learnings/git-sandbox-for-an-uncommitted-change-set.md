# Giving a tool a writable copy of an uncommitted change set

An agent that edits files needs somewhere to edit them that is not the user's working tree — a
forked subagent's writes land outside the session's checkpoints, so `/rewind` cannot undo them,
and two agents writing at once collide. The obvious instrument is `git worktree`, and it does not
work on its own: a worktree checks out a *commit*, so it arrives without the uncommitted edits,
new files and deletions that are the entire subject of a commit review.

`claude/scripts/worktree-sandbox.py` closes that gap. The mechanism is a worktree plus a carry-in
scoped to the change set, and the scoping is the part that matters.

## What the alternatives do, measured

Four approaches were tested on 2026-09-30 before settling on this one. Each failed for a reason
worth keeping, because each looks right until it is run.

- **`git stash create`** records untracked files not at all. It produced a two-parent commit with
  no untracked tree, so `git stash apply` had nothing to restore and a new file was simply absent
  from the sandbox. The `--include-untracked` flag does not change this.
- **`git stash push --include-untracked`** does record them — three parents — but it *removes the
  files from the user's tree*, leaving `git status` empty until something pops them back. A
  background agent that fails between the push and the pop has taken the user's work with it.
- **A whole-tree copy** works and is fast where the filesystem has copy-on-write: `cp -c -R` of a
  15 MB repo took 245 ms on APFS and carried the tracked edits, the untracked files, the ignored
  files, `.git`, and left transcrypt-encrypted files readable. It is still the wrong answer,
  because a working tree is not bounded by its repository: one repo on this machine is **38 GB**
  against a 23 MB `.git`, all of it build output. Windows has no copy-on-write to fall back on.
- **The harness's own worktree isolation** — `EnterWorktree`, and `isolation: worktree` on a
  subagent — branches from `origin/<default>` or local `HEAD` depending on `worktree.baseRef`.
  Both are committed states, so it carries no dirty files either. Same gap, by contract.

## The shape that works

A worktree at `HEAD` shares `.git`, so nothing is duplicated and transcrypt keys, hooks and config
all come along. On top of it, copy in only the paths `git status --porcelain -z -uall` names,
both halves of a rename, deleting in the sandbox whatever no longer exists in the source. Then
commit that state inside the sandbox on a detached HEAD, so a later `git diff HEAD` shows what the
*tool* changed rather than the change set it was handed.

Cost is O(change set), not O(working tree), which is what makes it survive the 38 GB repo:
measured on a 200 MB scratch repo whose bulk was one ignored blob, a 3-path change set took 35 ms
and produced a 16 KB sandbox whose `git status` mirrored the source exactly, deletion and
untracked file included. On the real dotfiles repo, a 14-path change set gave a 6.1 MB sandbox,
and the patch it yielded applied to the real tree under `git apply --check`.

## Three limits to carry into any caller

**Ignored files are excluded by construction.** That is correct for reviewing documentation or
source, and wrong for anything that needs a build artifact — such a caller must copy what it needs
itself rather than concluding the file is absent.

**A file the tool creates is untracked in the sandbox, and a plain `git diff` omits it.** `git add
-N` it there, or the patch silently loses a new file. The `patch` subcommand warns on stderr about
any it finds, which is the one output of this flow that must not be ignored.

**Put the sandbox outside the repository.** `.claude/worktrees/` is where `EnterWorktree` puts its
own, and it is not in every repo's `.gitignore` — the dotfiles repo does not ignore it. A sandbox
there shows up as untracked in the very change set being reviewed.

A rename is covered only because its source is in that list as well as its destination: handed
the destination alone, the carry-in copies the new file and never deletes the old one. Symlinks
and submodules are untested.
