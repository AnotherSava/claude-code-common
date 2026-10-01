#!/usr/bin/env python3
"""Give a sub-skill a writable copy of the pending change set, outside the user's tree.

A git worktree checks out a commit, so it arrives without the uncommitted and untracked files
that are the whole subject of a commit review. This carries them in, scoped to the change set
rather than the working tree: measured 2026-09-30 on a 200 MB repo whose bulk was one ignored
blob, a 3-path change set took 35 ms and produced a 16 KB sandbox.

    worktree-sandbox.py create            # prints the sandbox path on the last line
    worktree-sandbox.py patch <path>      # what the sub-skill changed, as a unified diff
    worktree-sandbox.py remove <path>

The sandbox lives under the system temp directory, never inside the repo: `.claude/worktrees/`
is not ignored in every repo, and a sandbox there would show up as untracked in the change set
being reviewed.

Ignored files are not carried in. That is right for a review of documentation or source, and
wrong for anything needing a build artifact — such a caller must copy what it needs itself.
Renames arrive as their destination path. Symlinks and submodules are untested.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "shared"))
from git_changeset import changed_paths, git  # noqa: E402  (the shared module's path is set above)

CARRIED_MARKER = "sandbox: carried-in change set"


def repo_root() -> str:
    return git(["rev-parse", "--show-toplevel"]).strip()


def carry_in(root: str, sandbox: str, paths: list[str]) -> tuple[int, int]:
    """Reproduce the change set inside the sandbox. Returns (files copied, files deleted)."""
    copied = deleted = 0
    for path in paths:
        source = os.path.join(root, path)
        target = os.path.join(sandbox, path)
        if os.path.exists(source):
            os.makedirs(os.path.dirname(target) or sandbox, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
        elif os.path.exists(target):
            os.remove(target)
            deleted += 1
    return copied, deleted


def create(name: str | None) -> None:
    root = repo_root()
    sandbox = os.path.join(tempfile.mkdtemp(prefix="cc-sandbox-"), name or "tree")
    git(["worktree", "add", "--detach", "--quiet", sandbox, "HEAD"], cwd=root)

    paths = changed_paths(cwd=root)
    copied, deleted = carry_in(root, sandbox, paths)

    # Commit the incoming state so a later `git diff HEAD` shows only what the sub-skill changed,
    # not the change set it was handed. Detached HEAD, so no branch name can collide.
    git(["add", "-A"], cwd=sandbox)
    if git(["status", "--porcelain"], cwd=sandbox).strip():
        git(["-c", "user.name=sandbox", "-c", "user.email=sandbox@localhost",
             "commit", "--no-gpg-sign", "--quiet", "-m", CARRIED_MARKER], cwd=sandbox)

    print(f"carried {copied} file(s) in, {deleted} deletion(s), from a {len(paths)}-path change set")
    print("ignored files were not carried in; copy any build artifact you need yourself")
    print(sandbox)


def patch(sandbox: str, binary: bool) -> None:
    """The sub-skill's own edits — the carried-in state is the baseline commit, so HEAD is it."""
    args = ["diff", "HEAD"]
    if binary:
        args.append("--binary")
    out = git(args, cwd=sandbox, binary=True)
    untracked = git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=sandbox, binary=True)
    if untracked.strip(b"\0"):
        names = ", ".join(p.decode("utf-8", "surrogateescape") for p in untracked.split(b"\0") if p)
        print(f"# NOTE: {names} is untracked in the sandbox and absent from this diff; "
              f"`git add -N` it there first to include it", file=sys.stderr)
    sys.stdout.buffer.write(out)


def remove(sandbox: str) -> None:
    root = repo_root()
    git(["worktree", "remove", "--force", sandbox], cwd=root)
    git(["worktree", "prune"], cwd=root)
    parent = os.path.dirname(os.path.abspath(sandbox))
    if os.path.basename(parent).startswith("cc-sandbox-") and not os.listdir(parent):
        os.rmdir(parent)
    print(f"removed {sandbox}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    made = sub.add_parser("create", help="make a sandbox holding the pending change set")
    made.add_argument("--name", help="directory name for the sandbox, for a readable path")
    got = sub.add_parser("patch", help="print what the sub-skill changed inside the sandbox")
    got.add_argument("sandbox")
    got.add_argument("--binary", action="store_true", help="include binary file changes")
    gone = sub.add_parser("remove", help="tear the sandbox down")
    gone.add_argument("sandbox")
    args = parser.parse_args()

    if args.action == "create":
        create(args.name)
    elif args.action == "patch":
        patch(args.sandbox, args.binary)
    else:
        remove(args.sandbox)


if __name__ == "__main__":
    main()
