#!/usr/bin/env python3
"""Cases for `claude/skills/shared/gate_pushed_tree.py`, the gate run before every push.

Its costly failure is a skip over a tree the gate never passed, since nothing after it measures the push. So most
cases try to make the pre-push run skip when it must not: a file held back from the commits, an edit made after the
pre-commit run, a record left over from an earlier run, a gate that failed or rewrote what it checked. Each runs
against a real clone of a bare origin, sealed from this machine's git config, with a stub gate that counts its runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from git_scratch import check, failures, seal, sh, write

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "shared", "gate_pushed_tree.py")

# Counts each run into $GATE_COUNT; $GATE_MODE makes it fail, or rewrite a tracked file the way a formatter would.
STUB_GATE = """#!/usr/bin/env bash
echo run >> "$GATE_COUNT"
case "${GATE_MODE:-pass}" in
  fail) exit 3 ;;
  rewrite) echo formatted > app.txt ;;
esac
exit 0
"""

def commit_all(repo: str) -> None:
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", "change")


def gate(repo: str, *flags: str, mode: str = "pass") -> tuple[int, str]:
    env = {**os.environ, "GATE_MODE": mode}
    done = subprocess.run([sys.executable, SCRIPT, "--caller", "commit", *flags], cwd=repo, capture_output=True, text=True, timeout=120, env=env)
    return done.returncode, done.stdout


def runs() -> int:
    if not os.path.exists(os.environ["GATE_COUNT"]):
        return 0
    with open(os.environ["GATE_COUNT"], encoding="utf-8") as handle:
        return len(handle.read().split())


def fresh(scratch: str, name: str) -> str:
    """A clone with the stub gate pushed and one pending change in the working tree."""
    origin = os.path.join(scratch, f"{name}.git")
    repo = os.path.join(scratch, name)
    subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
    subprocess.run(["git", "clone", "-q", origin, repo], check=True, capture_output=True)
    os.makedirs(os.path.join(repo, ".claude"))
    write(repo, ".claude/commit-checks.sh", STUB_GATE)
    write(repo, ".gitignore", "/build/\n")
    write(repo, "app.txt", "one\n")
    commit_all(repo)
    sh(repo, "push", "-q", "origin", "HEAD")
    write(repo, "app.txt", "two\n")
    write(repo, "new.txt", "untracked until committed\n")
    return repo


def main() -> int:
    scratch = tempfile.mkdtemp(prefix="gate-pushed-tree-test-")
    seal(scratch)
    os.environ.update({"GATE_COUNT": os.path.join(scratch, "count")})
    try:
        repo = fresh(scratch, "skip")
        code, out = gate(repo, "--record")
        check("the pre-commit run passes and records", (code, "recorded tree" in out), (0, True))
        check("the pre-commit run gates once", runs(), 1)
        os.makedirs(os.path.join(repo, "build"))
        write(repo, "build/out.bin", "ignored output\n")
        commit_all(repo)
        code, out = gate(repo)
        check("every file committed: the pre-push run skips", (code, "SKIPPED" in out), (0, True))
        check("and runs no gate", runs(), 1)
        code, out = gate(repo)
        check("the record is consumed, so the next run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "dirty-after")
        os.remove(os.environ["GATE_COUNT"])
        gate(repo, "--record")
        commit_all(repo)
        write(repo, "app.txt", "edited after the commit\n")
        code, out = gate(repo)
        check("an edit after the commits leaves HEAD's tree gated: the pre-push run skips", (code, "SKIPPED" in out, runs()), (0, True, 1))

        repo = fresh(scratch, "held")
        os.remove(os.environ["GATE_COUNT"])
        gate(repo, "--record")
        sh(repo, "add", "app.txt")
        sh(repo, "commit", "-qm", "only app")
        code, out = gate(repo)
        check("a file held back from the commits: the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "edited")
        os.remove(os.environ["GATE_COUNT"])
        gate(repo, "--record")
        write(repo, "app.txt", "edited after the gate\n")
        commit_all(repo)
        code, out = gate(repo)
        check("an edit after the pre-commit run: the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "stale")
        os.remove(os.environ["GATE_COUNT"])
        gate(repo, "--record")
        record = sh(repo, "rev-parse", "--git-path", "commit-gate-passed")
        record = record if os.path.isabs(record) else os.path.join(repo, record)
        with open(record, encoding="utf-8") as handle:
            tree = handle.read().split()[0]
        with open(record, "w", encoding="utf-8") as handle:
            handle.write(f"{tree} 1000000000\n")
        commit_all(repo)
        code, out = gate(repo)
        check("a record older than the age limit: the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "failed")
        os.remove(os.environ["GATE_COUNT"])
        code, out = gate(repo, "--record", mode="fail")
        check("a failing pre-commit run exits with the gate's code", (code, "FAILED" in out), (3, True))
        commit_all(repo)
        code, out = gate(repo)
        check("and leaves no record, so the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "rewrite")
        os.remove(os.environ["GATE_COUNT"])
        code, out = gate(repo, "--record", mode="rewrite")
        check("a gate that rewrites a file passes without recording", (code, "nothing is recorded" in out), (0, True))
        commit_all(repo)
        code, out = gate(repo)
        check("so the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 2))

        repo = fresh(scratch, "plain")
        os.remove(os.environ["GATE_COUNT"])
        commit_all(repo)
        code, out = gate(repo)
        check("with no pre-commit run at all, the pre-push run gates", (code, "SKIPPED" in out, runs()), (0, False, 1))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    for line in failures:
        print(line)
    print(f"gate-pushed-tree tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
