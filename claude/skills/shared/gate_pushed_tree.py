#!/usr/bin/env python3
"""Run a repo's commit gate over the state a push is about to publish, and say what it covered.

A gate run before the commits are made measures neither thing a push sends: commits made earlier —
by hand, by another tool, or by a session that skipped the gate — were never measured, and a gate
run against a working tree holding files the plan held back measures a tree the remote never gets.
Both are silent, because the gate reports green on a tree that resembles the right one.

Its plain run comes after every commit is made and before the push, so a clean tree is the normal case: the
working tree is then byte-identical to HEAD, and the gate's verdict binds the published state. A
dirty tree still gets the run, with the paths that make it differ named rather than glossed.

What it cannot see is permanent and gets said every time: interior revisions. The gate measures one
tree, so a commit in the middle of the range can hold a state nothing checked even when the tip
passes. Running it per commit needs a checkout per commit, which this repo cannot have — its
conventions assert the `~/.claude` symlinks and derive a project id from the checkout path, so any
scratch worktree collects 17 violations across two rules that have nothing to do with the tree.

Run twice by /yolo and /wrap-up, and so built to skip the second run when it would repeat the first.
/adopt also makes the --record run and pushes nothing, so its record can make the next push.py run
within RECORD_MAX_AGE skip. The skill calls it with --record, before any commit exists: it gates the working tree and, on a pass,
writes down the tree it measured. push.py calls it plainly, and when HEAD holds exactly that tree, it
reports SKIPPED instead of gating again. The gate reads one tree, the
tip, so a matching tree is the whole of what a second run would see; commits made before the skill
started were in the working tree the recorded run gated. What a match cannot vouch for is everything the
gate reads outside the tree — ignored build output, the `~/.claude` checker other repos' gates
call — so the record is consumed by the next plain run and expires after RECORD_MAX_AGE, which
keeps the skip inside one skill run rather than letting a stale pass stand for a later push.

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
import time

from git_changeset import changed_paths, git

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from review_scope import worktree_tree

GATE = ".claude/commit-checks.sh"
# Under the git dir, so every repo has a place for it whether or not it keeps a gitignored tmp/.
RECORD = "commit-gate-passed"
RECORD_MAX_AGE = 3600


def _unpushed(root: str) -> list[str]:
    """Commits no remote ref contains — the range a push would publish.

    `HEAD --not --remotes` rather than `@{upstream}..HEAD`: it needs no tracking branch, and it
    stays right in a fork whose branch tracks `upstream` while pushes go to `origin`, where the
    upstream form counts every already-pushed commit as unpushed forever.
    """
    return [line for line in git(["rev-list", "HEAD", "--not", "--remotes"], cwd=root).splitlines() if line]


def _record_path(root: str) -> str:
    path = git(["rev-parse", "--git-path", RECORD], cwd=root).strip()
    return path if os.path.isabs(path) else os.path.join(root, path)


def _take_record(root: str) -> str | None:
    """The tree the last --record run passed, if it is recent enough to vouch for, removed as it is read."""
    path = _record_path(root)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        tree, _, stamp = handle.read().strip().partition(" ")
    os.remove(path)
    return tree if stamp.isdigit() and time.time() - int(stamp) <= RECORD_MAX_AGE else None


def _find_bash() -> str:
    # A bare "bash" goes through CreateProcess on Windows, which searches System32 before PATH and
    # so starts the WSL launcher, a different OS with none of the tools the gate calls. A PATH
    # search finds Git Bash there. See learnings/windows-spawning-bash.md.
    bash = shutil.which("bash")
    if bash is None:
        print("gate-pushed-tree: UNMEASURED — no bash on PATH to run the gate with")
        sys.exit(1)
    return bash


def _run_gate(root: str, bash: str) -> int:
    done = subprocess.run([bash, GATE], cwd=root, capture_output=True, text=True)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


def _record(root: str, bash: str) -> None:
    """Gate the working tree and, on a pass, write down the tree it measured.

    The tree is taken before and after the run and recorded only when the two agree, so a gate that
    rewrites a file it checks (a formatter) leaves no record of a tree it never measured whole.
    """
    if os.path.exists(_record_path(root)):
        os.remove(_record_path(root))
    before = worktree_tree(root)
    print(f"gate-pushed-tree: running {GATE} over the working tree")
    code = _run_gate(root, bash)
    if code != 0:
        print(f"gate-pushed-tree: FAILED (exit {code}) — the change set does not pass this repo's own gate")
        sys.exit(code)
    if worktree_tree(root) != before:
        print("gate-pushed-tree: PASSED, but the gate changed the working tree, so nothing is recorded and the pre-push run will gate again")
        return
    with open(_record_path(root), "w", encoding="utf-8") as handle:
        handle.write(f"{before} {int(time.time())}\n")
    print(f"gate-pushed-tree: PASSED, and recorded tree {before[:12]} so a pre-push run over the same tree can skip")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Taken without its slash: Git Bash rewrites an argument like "/yolo" into a Windows path
    # ("C:/Program Files/Git/commit") before Python sees it.
    parser.add_argument("--caller", required=True, help="skill name without the leading slash, for the report lines")
    parser.add_argument("--record", action="store_true", help="gate the working tree before committing and record the tree that passed")
    args = parser.parse_args()
    skill = f"/{args.caller}"

    try:
        root = git(["rev-parse", "--show-toplevel"]).strip()
    except subprocess.CalledProcessError:
        print("gate-pushed-tree: NOT COVERED — not inside a git repository")
        return

    if args.record:
        if not os.path.exists(os.path.join(root, GATE)):
            print(f"gate-pushed-tree: NOT COVERED — this repo has no {GATE}")
            return
        _record(root, _find_bash())
        return

    recorded = _take_record(root)

    try:
        commits = _unpushed(root)
    except subprocess.CalledProcessError as exc:
        print(f"gate-pushed-tree: UNMEASURED — the unpushed range could not be read: {exc.stderr.strip()}")
        sys.exit(1)

    if not commits:
        print(f"gate-pushed-tree: nothing unpushed, so {skill} would publish no new state")
        return

    if not os.path.exists(os.path.join(root, GATE)):
        print(f"gate-pushed-tree: NOT COVERED — {len(commits)} unpushed commit(s) and this repo has no {GATE}")
        return

    # HEAD's tree is what the push publishes, so a dirty working tree does not stop the skip: the
    # files that make it dirty reach neither the remote nor the tree the record vouches for.
    if recorded is not None and recorded == git(["rev-parse", "HEAD^{tree}"], cwd=root).strip():
        print("gate-pushed-tree: SKIPPED — HEAD's tree is the one the pre-commit run gated, so this run would measure nothing new")
        print("gate-pushed-tree: interior revisions in the range are unchecked either way — the gate measures one tree, never each commit's")
        return

    bash = _find_bash()
    held = sorted(set(changed_paths(cwd=root)))
    print(f"gate-pushed-tree: running {GATE} over the {len(commits)} unpushed commit(s) {skill} would publish")
    code = _run_gate(root, bash)
    if code != 0:
        print(f"gate-pushed-tree: FAILED (exit {code}) — do not push; the published state would not pass this repo's own gate")
        sys.exit(code)

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
