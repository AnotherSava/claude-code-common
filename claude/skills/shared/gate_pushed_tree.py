#!/usr/bin/env python3
"""Run a repo's commit gate over the state a push is about to publish, and say what it covered.

A gate run before the commits are made measures neither thing a push sends: commits made earlier —
by hand, by another tool, or by a session that skipped the gate — were never measured, and a gate
run against a working tree holding files the plan held back measures a tree the remote never gets.
Both are silent, because the gate reports green on a tree that resembles the right one.

This runs after every commit is made and before the push, so a clean tree is the normal case: the
working tree is then byte-identical to HEAD, and the gate's verdict binds the published state. A
dirty tree still gets the run, with the paths that make it differ named rather than glossed.

What it cannot see is permanent and gets said every time: interior revisions. The gate measures one
tree, so a commit in the middle of the range can hold a state nothing checked even when the tip
passes. Running it per commit needs a checkout per commit, which this repo cannot have — its
conventions assert the `~/.claude` symlinks and derive a project id from the checkout path, so any
scratch worktree collects 17 violations across two rules that have nothing to do with the tree.

Called by every skill that pushes. Exits non-zero when the gate fails, when the unpushed range
cannot be read at all, and when no bash is on PATH to run the gate — an unmeasured range is not a
pass. A repo with no gate, and a directory that is not a repo, are reported as NOT COVERED and
block nothing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from git_changeset import changed_paths, git

GATE = ".claude/commit-checks.sh"


def unpushed(root: str) -> list[str]:
    """Commits no remote ref contains — the range a push would publish.

    `HEAD --not --remotes` rather than `@{upstream}..HEAD`: it needs no tracking branch, and it
    stays right in a fork whose branch tracks `upstream` while pushes go to `origin`, where the
    upstream form counts every already-pushed commit as unpushed forever.
    """
    return [line for line in git(["rev-list", "HEAD", "--not", "--remotes"], cwd=root).splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Taken without its slash: Git Bash rewrites an argument like "/commit" into a Windows path
    # ("C:/Program Files/Git/commit") before Python sees it.
    parser.add_argument("--caller", required=True, help="skill name without the leading slash, for the report lines")
    args = parser.parse_args()
    skill = f"/{args.caller}"

    try:
        root = git(["rev-parse", "--show-toplevel"]).strip()
    except subprocess.CalledProcessError:
        print("gate-pushed-tree: NOT COVERED — not inside a git repository")
        return

    try:
        commits = unpushed(root)
    except subprocess.CalledProcessError as exc:
        print(f"gate-pushed-tree: UNMEASURED — the unpushed range could not be read: {exc.stderr.strip()}")
        sys.exit(1)

    if not commits:
        print(f"gate-pushed-tree: nothing unpushed, so {skill} would publish no new state")
        return

    if not os.path.exists(os.path.join(root, GATE)):
        print(f"gate-pushed-tree: NOT COVERED — {len(commits)} unpushed commit(s) and this repo has no {GATE}")
        return

    # A bare "bash" goes through CreateProcess on Windows, which searches System32 before PATH and
    # so starts the WSL launcher, a different OS with none of the tools the gate calls. A PATH
    # search finds Git Bash there. See learnings/windows-spawning-bash.md.
    bash = shutil.which("bash")
    if bash is None:
        print("gate-pushed-tree: UNMEASURED — no bash on PATH to run the gate with")
        sys.exit(1)

    held = sorted(set(changed_paths(cwd=root)))
    print(f"gate-pushed-tree: running {GATE} over the {len(commits)} unpushed commit(s) {skill} would publish")
    done = subprocess.run([bash, GATE], cwd=root, capture_output=True, text=True)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)

    if done.returncode != 0:
        print(f"gate-pushed-tree: FAILED (exit {done.returncode}) — do not push; the published state would not pass this repo's own gate")
        sys.exit(done.returncode)

    if held:
        print(f"gate-pushed-tree: PASSED on the working tree, which is NOT the tree a push publishes — {len(held)} path(s) differ:")
        for path in held:
            print(f"  {path}")
        print("gate-pushed-tree: so the verdict binds the published state only where those paths do not bear on it — judge that before pushing")
    else:
        print("gate-pushed-tree: PASSED, and the tree is clean, so this verdict is the published state's own")
    print("gate-pushed-tree: interior revisions in the range are unchecked either way — the gate measures one tree, never each commit's")


if __name__ == "__main__":
    main()
