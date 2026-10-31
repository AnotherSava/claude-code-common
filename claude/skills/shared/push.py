#!/usr/bin/env python3
"""Publish the current branch: gate the tree a push would send, push, publish the review bookmark, ask the other
machine to pull, and end on the bookmark's state.

Every skill that pushes the default branch calls this one script, so the steps that must follow a push cannot be left
out by one of them. `/pr-create` is the exception: it force-pushes a feature branch with `--force-with-lease`, which
this script has no mode for, so a step added here does not reach that push.

In order:

1. `gate_pushed_tree.py` over the state the push would publish; a failing gate refuses the push.
2. `git push`, or `git push -u origin HEAD` when the branch tracks nothing yet, reading from git's report where the
   pushed branch stood before it (`none` for a new branch).
3. `review_scope.py push`, so the other machine's next review starts from this bookmark.
4. `notify_peer_pull.py`, asking the other machine's session on this project to `/pull`.
5. The CI runs the push started, when the repo has workflows: their ids and the command to watch each. A repo
   without `.github/workflows/` has no CI, and says nothing about it.
6. `review_scope.py status`, last, so whether the bookmark moved is read at the end of the report.

Exit codes: 0 pushed, 1 refused (gate failed, or git refused the push), 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "scripts")
REVIEW_SCOPE = os.path.join(SCRIPTS, "review_scope.py")


def _run(*cmd: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True)


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return _run("git", *args, cwd=repo)


def _ci_runs(repo: str, sha: str) -> list[str]:
    """One line per run the push started, or a line saying they could not be listed. `gh run list --commit` lags the
    push and can answer with a subset of the runs (measured in `learnings/gh-cli.md`), so fewer runs than workflow
    files adds a re-query line; the caller watches each in the background."""
    workflows = os.path.join(repo, ".github", "workflows")
    if not os.path.isdir(workflows):
        return []
    listed = _run("gh", "run", "list", "--commit", sha, "--json", "databaseId,workflowName,status", cwd=repo)
    if listed.returncode != 0:
        return [f"ci: the repo has workflows, but `gh run list` failed, so their result is unknown: {listed.stderr.strip()}"]
    runs = json.loads(listed.stdout or "[]")
    if not runs:
        return [f"ci: no run listed yet for {sha[:12]} — the list lags a push; re-query with `gh run list --commit {sha}`"]
    lines = [f"ci: {run['workflowName']} {run['status']} — watch with `gh run watch {run['databaseId']} --exit-status --compact`" for run in runs]
    # A workflow file that never triggers on a push (a tag release, a manual dispatch) also counts here, so a short list
    # asks for a re-query rather than reporting a run as missing.
    files = [name for name in os.listdir(workflows) if name.endswith((".yml", ".yaml"))]
    if len(runs) < len(files):
        lines.append(f"ci: {len(runs)} run(s) listed for {len(files)} workflow file(s) — the list lags a push; re-query with `gh run list --commit {sha}` until every workflow a push triggers is listed")
    return lines


def _pushed_from(porcelain: str, head: str) -> str:
    """Where the pushed branch stood on the remote, read from git's own report of the push. Neither `@{upstream}` nor
    `@{push}` gives it: a fork tracking `upstream` with remote.pushDefault=origin pushes to origin, where `@{upstream}`
    names the third-party tip and `@{push}` cannot resolve under `push.default=simple`."""
    for line in porcelain.splitlines():
        fields = line.split("\t")
        if len(fields) < 3 or ":" not in fields[1]:
            continue
        summary = fields[2].split()[0] if fields[2].split() else ""
        if ".." in summary:
            return summary.split("..")[0]
        return head if summary.startswith("[up") else "none"
    return "none"


def push(repo: str, caller: str) -> int:
    gate = _run(sys.executable, os.path.join(HERE, "gate_pushed_tree.py"), "--caller", caller, cwd=repo)
    print(gate.stdout.rstrip())
    if gate.returncode != 0:
        print("NOT PUSHED: the gate failed over the state the push would publish")
        return 1

    upstream = _git(repo, "rev-parse", "@{upstream}")
    pushed = _git(repo, "push", "--porcelain") if upstream.returncode == 0 else _git(repo, "push", "--porcelain", "-u", "origin", "HEAD")
    if pushed.returncode != 0:
        print(f"NOT PUSHED: git push failed:\n{pushed.stderr.strip()}")
        return 1
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _pushed_from(pushed.stdout, head)
    print(f"pushed: {before[:12] if before != 'none' else 'none'}..{head[:12]}")

    for line in (_run(sys.executable, REVIEW_SCOPE, "push", cwd=repo).stdout.strip(),
                 _run(sys.executable, os.path.join(HERE, "notify_peer_pull.py"), before, caller, cwd=repo).stdout.strip(),
                 *_ci_runs(repo, head),
                 _run(sys.executable, REVIEW_SCOPE, "status", cwd=repo).stdout.strip()):
        if line:
            print(line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--caller", required=True, help="the pushing skill's name without the slash, for the reports and the peer notice")
    parser.add_argument("--repo", default=".")
    opts = parser.parse_args()
    top = _git(os.path.abspath(opts.repo), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print(f"ERROR: not a git repository: {opts.repo}")
        return 2
    return push(top.stdout.strip(), opts.caller)


if __name__ == "__main__":
    sys.exit(main())
