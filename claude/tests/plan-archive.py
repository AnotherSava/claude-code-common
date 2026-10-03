#!/usr/bin/env python3
"""Cases for `claude/hooks/plan-archive.py start`.

The hook runs unattended at every plan approval on both machines, and both of its failures are
quiet: a plan filed into a repo that is not the user's sits untracked among someone else's design
docs until a commit sweeps it into a pull request, and a plan moved rather than copied exists
nowhere once that working tree is cleaned. Each case runs the real hook as a subprocess against a
scratch repo, with HOME pointed at a scratch directory so `~/.claude/plans/` and the log are its own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, "claude", "hooks", "plan-archive.py")

sys.path.insert(0, os.path.join(ROOT, "claude", "conventions"))
import engine  # noqa: E402 — needs the sys.path line above

failures: list[str] = []

PLAN = "# Wire the widget into the frame\n\n## Context\n\nBody.\n"
OTHER = "# Another session's plan\n\nNot this one.\n"


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def git(args: list[str], cwd: str) -> None:
    subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)


def make_repo(path: str, remotes: dict[str, str]) -> None:
    os.makedirs(path)
    git(["init", "-q", "."], path)
    for name, url in remotes.items():
        git(["remote", "add", name, url], path)


def approve(work: str, cwd: str, text: str = PLAN, response: object = None) -> str:
    """Run the hook from `cwd` with a scratch HOME, as Claude Code runs it after an approval.

    The session's plan file is written into the scratch ~/.claude/plans/ as Claude Code leaves it, and
    a second, fresher plan from another session sits beside it, so a hook that picks a plan by mtime
    rather than from its payload files the wrong one. Returns the session's plan file path.
    """
    home = os.path.join(work, "home")
    plans = os.path.join(home, ".claude", "plans")
    os.makedirs(plans)
    plan = os.path.join(plans, "zesty-coalescing-crystal.md")
    with open(plan, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    # Five seconds older than the other session's plan: both inside any recency window, the other
    # strictly newer, so an mtime pick cannot land on this one by a tie.
    stamp = time.time()
    os.utime(plan, (stamp - 5, stamp - 5))
    with open(os.path.join(plans, "other-session-plan.md"), "w", encoding="utf-8") as handle:
        handle.write(OTHER)
    if response is None:
        response = {"plan": text, "isAgent": False, "filePath": plan}
    payload = {"cwd": cwd, "hook_event_name": "PostToolUse", "tool_name": "ExitPlanMode", "tool_input": {"plan": text, "planFilePath": plan}, "tool_response": response}
    env = dict(os.environ, HOME=home, USERPROFILE=home)
    done = subprocess.run([sys.executable, "-S", HOOK, "start"], input=json.dumps(payload), env=env, capture_output=True, text=True)
    check(f"{cwd}: hook exits 0", done.returncode, 0)
    check(f"{cwd}: hook prints nothing", done.stdout + done.stderr, "")
    try:
        with open(plan, encoding="utf-8", newline="") as handle:
            left = handle.read()
    except OSError:
        left = None
    check(f"{cwd}: the session's plan file is left as it was", left, text)
    return plan


def filed(directory: str) -> list[str]:
    plans = os.path.join(directory, "docs", "plans")
    return sorted(os.listdir(plans)) if os.path.isdir(plans) else []


def case_own_repo_from_subdirectory(base: str) -> None:
    work = os.path.join(base, "own")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "git@github.com:AnotherSava/widget.git"})
    sub = os.path.join(repo, "src", "deep")
    os.makedirs(sub)
    approve(work, sub)
    names = filed(repo)
    check("own repo: one plan filed at the repo root", len(names), 1)
    check("own repo: slug comes from the H1", bool(names) and names[0].endswith("_wire-the-widget-into-the-frame.md"), True)
    check("own repo: nothing filed under the subdirectory", filed(sub), [])
    if names:
        with open(os.path.join(repo, "docs", "plans", names[0]), encoding="utf-8") as handle:
            check("own repo: the copy carries the plan verbatim", handle.read(), PLAN)


def case_fork(base: str) -> None:
    work = os.path.join(base, "fork")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "git@github.com:AnotherSava/widget.git", "upstream": "git@github.com:someone-else/widget.git"})
    approve(work, repo)
    check("fork: nothing filed", filed(repo), [])
    check("fork: no docs/ created", os.path.exists(os.path.join(repo, "docs")), False)


def case_third_party(base: str) -> None:
    work = os.path.join(base, "third")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "https://github.com/someone-else/widget.git"})
    approve(work, repo)
    check("third-party clone: nothing filed", filed(repo), [])


def case_no_origin(base: str) -> None:
    # A repo with no remote yet is still one of ours, as the engine reads it.
    work = os.path.join(base, "fresh")
    repo = os.path.join(work, "repo")
    make_repo(repo, {})
    approve(work, repo)
    check("repo with no origin: one plan filed", len(filed(repo)), 1)


def case_not_a_repo(base: str) -> None:
    work = os.path.join(base, "plain")
    folder = os.path.join(work, "folder")
    os.makedirs(folder)
    if engine.repo_root(folder) is not None:
        failures.append(f"  NOT COVERED not-a-repo case: the scratch directory sits inside a repo at {engine.repo_root(folder)}")
        return
    approve(work, folder)
    check("not a repo: one plan filed under the cwd", len(filed(folder)), 1)


def case_no_title(base: str) -> None:
    work = os.path.join(base, "untitled")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "git@github.com:AnotherSava/widget.git"})
    approve(work, repo, "## Context\n\nNo title here.\n")
    names = filed(repo)
    check("no H1: falls back to the codename", bool(names) and names[0].endswith("_zesty-coalescing-crystal.md"), True)
    if names:
        with open(os.path.join(repo, "docs", "plans", names[0]), encoding="utf-8") as handle:
            check("no H1: the copy carries the warning marker", handle.read().startswith("<!-- plan-archive: no `# H1 Title`"), True)


def case_no_plan_in_payload(base: str) -> None:
    # Without the approved text in the payload there is nothing that identifies this session's plan,
    # and the newest file in ~/.claude/plans/ may be another session's.
    work = os.path.join(base, "noplan")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "git@github.com:AnotherSava/widget.git"})
    approve(work, repo, response="Plan approved")
    check("payload without a plan: nothing filed", filed(repo), [])


def case_line_endings(base: str) -> None:
    work = os.path.join(base, "crlf")
    repo = os.path.join(work, "repo")
    make_repo(repo, {"origin": "git@github.com:AnotherSava/widget.git"})
    text = PLAN.replace("\n", "\r\n")
    approve(work, repo, text)
    names = filed(repo)
    if names:
        with open(os.path.join(repo, "docs", "plans", names[0]), "rb") as handle:
            check("line endings: the copy keeps the plan's bytes", handle.read(), text.encode("utf-8"))
    else:
        check("line endings: one plan filed", names, ["<one plan>"])


def main() -> None:
    base = tempfile.mkdtemp(prefix="plan-archive-test-")
    try:
        for case in (case_own_repo_from_subdirectory, case_fork, case_third_party, case_no_origin, case_not_a_repo, case_no_title, case_no_plan_in_payload, case_line_endings):
            case(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    for line in failures:
        print(line)
    print(f"plan-archive tests: {'all cases behave' if not failures else f'{len(failures)} failure(s)'}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
