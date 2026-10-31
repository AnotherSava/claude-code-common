#!/usr/bin/env python3
"""Cases for `claude/skills/shared/push.py`, the push every skill pushing the default branch makes.

Its costly failures are a push that goes out over a failing gate, and a report that leaves out what follows a push:
the bookmark's state, or a CI line where CI exists. Each case runs against a real clone of a bare origin, sealed
from this machine's git config, with a stub gate and the dashboard pointed at a port nothing listens on, so no peer
is ever messaged.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from git_scratch import check, commit, failures, seal, sh, write

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "shared", "push.py")

STUB_GATE = """#!/usr/bin/env bash
case "${GATE_MODE:-pass}" in fail) exit 3 ;; esac
exit 0
"""

def run(repo: str, mode: str = "pass") -> tuple[int, list[str]]:
    env = {**os.environ, "GATE_MODE": mode}
    done = subprocess.run([sys.executable, SCRIPT, "--caller", "yolo", "--repo", repo], capture_output=True, text=True, timeout=180, env=env)
    return done.returncode, [line for line in done.stdout.splitlines() if line.strip()]


def clone(scratch: str, name: str, push_first: bool = True) -> tuple[str, str]:
    origin = os.path.join(scratch, f"{name}.git")
    repo = os.path.join(scratch, name)
    subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
    subprocess.run(["git", "clone", "-q", origin, repo], check=True, capture_output=True)
    write(repo, ".claude/commit-checks.sh", STUB_GATE)
    commit(repo, "app.txt", "one\n")
    if push_first:
        sh(repo, "push", "-q", "-u", "origin", "HEAD")
    return origin, repo


def main() -> int:
    scratch = tempfile.mkdtemp(prefix="push-test-")
    try:
        seal(scratch, "[push]\n\tdefault = current\n")
        os.environ.update({"TAURI_DASHBOARD_URL": "http://127.0.0.1:9"})

        origin, repo = clone(scratch, "gated")
        commit(repo, "app.txt", "two\n")
        before = sh(origin, "rev-parse", "main")
        code, lines = run(repo, "fail")
        check("a failing gate refuses", (code, any(line.startswith("NOT PUSHED") for line in lines)), (1, True))
        check("and nothing reaches origin", sh(origin, "rev-parse", "main"), before)

        code, lines = run(repo)
        check("a passing gate pushes", (code, sh(origin, "rev-parse", "main")), (0, sh(repo, "rev-parse", "HEAD")))
        check("the bookmark status is the last line", lines[-1].startswith("review bookmark:") if lines else False, True)
        check("the peer notice is reported", any(line.startswith("peer-pull:") for line in lines), True)
        check("a repo without workflows says nothing about CI", [line for line in lines if line.startswith("ci:")], [])

        origin, fresh = clone(scratch, "first", push_first=False)
        code, lines = run(fresh)
        check("a first push sets up tracking", (code, sh(fresh, "rev-parse", "--abbrev-ref", "@{upstream}")), (0, "origin/main"))
        check("and reports the remote as none before it", any(line.startswith("pushed: none..") for line in lines), True)

        origin, ci = clone(scratch, "ci")
        commit(ci, ".github/workflows/build.yml", "on: push\n")
        code, lines = run(ci)
        check("a repo with workflows gets a CI line", (code, any(line.startswith("ci:") for line in lines)), (0, True))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print("\n".join(failures))
        print(f"push tests: {len(failures)} failure(s)")
        return 1
    print("push tests: all cases behave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
