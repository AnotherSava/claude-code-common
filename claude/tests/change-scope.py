#!/usr/bin/env python3
"""Cases for `claude/skills/commit/scripts/change_scope.py`, the verdict /commit reads before its clean-up passes.

A wrong `SKIP` sends code to a commit that no clean-up pass looked at, and nothing later notices; a wrong `RUN` only
costs time. So the cases lean on the skips: the polish record the review-auto workflow leaves, and the images that
decide whether screenshots are checked. Each runs the script for real against a scratch repo and its bare origin,
sealed from this machine's git config.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "skills", "commit", "scripts", "change_scope.py")
sys.path.insert(0, os.path.join(ROOT, "claude", "scripts"))

import review_scope  # noqa: E402 — needs the sys.path line above

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def sh(repo: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def write(repo: str, name: str, text: str) -> None:
    path = os.path.join(repo, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def verdicts(repo: str) -> dict[str, str]:
    done = subprocess.run([sys.executable, SCRIPT], cwd=repo, capture_output=True, text=True, timeout=60)
    check("the script exits 0", (done.returncode, done.stderr), (0, ""))
    lines = [line.split(": ", 1) for line in done.stdout.splitlines() if line.split(":", 1)[0] in ("clean-code", "docs-relevance", "screenshot-relevance")]
    return {name: text for name, text in lines}


def polish(repo: str) -> None:
    """What a converged review-auto run leaves behind."""
    review_scope.mark(repo, review_scope.plan(repo)["base"], None, True)


def main() -> int:
    scratch = tempfile.mkdtemp(prefix="change-scope-test-")
    os.environ.update({"GIT_CONFIG_GLOBAL": os.path.join(scratch, "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"})
    with open(os.environ["GIT_CONFIG_GLOBAL"], "w", encoding="utf-8") as handle:
        handle.write("[user]\n\tname = t\n\temail = t@example.invalid\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
    try:
        origin, repo = os.path.join(scratch, "origin.git"), os.path.join(scratch, "repo")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
        subprocess.run(["git", "clone", "-q", origin, repo], check=True, capture_output=True)
        write(repo, "app.py", "one\n")
        sh(repo, "add", "-A")
        sh(repo, "commit", "-qm", "first")
        sh(repo, "push", "-q", "-u", "origin", "main")

        write(repo, "app.py", "two\n")
        got = verdicts(repo)
        check("a code change with no polish record runs both clean-up passes", (got["clean-code"].startswith("RUN"), got["docs-relevance"].startswith("RUN")), (True, True))
        check("and skips screenshots when the docs hold no images", got["screenshot-relevance"], "SKIP (the docs hold no images)")

        polish(repo)
        got = verdicts(repo)
        check("a polished tree skips clean-code", got["clean-code"], "SKIP (review-auto polished this tree)")
        check("and docs-relevance", got["docs-relevance"], "SKIP (review-auto polished this tree)")

        write(repo, ".claude/memory/learned.md", "written by /reflect after the review\n")
        got = verdicts(repo)
        check("a memory written after the polish still skips", got["clean-code"], "SKIP (review-auto polished this tree, 1 other path(s) changed since)")

        write(repo, "CLAUDE.md", "a line /reflect added after the review\n")
        got = verdicts(repo)
        check("a doc written after the polish still skips clean-code", got["clean-code"], "SKIP (review-auto polished this tree, 2 other path(s) changed since)")
        check("but runs docs-relevance again", got["docs-relevance"].startswith("RUN"), True)

        write(repo, "app.py", "three, edited after the polish\n")
        got = verdicts(repo)
        check("code edited after the polish runs clean-code again", got["clean-code"], "RUN (1 code file(s) changed)")
        check("and docs-relevance", got["docs-relevance"].startswith("RUN"), True)

        write(repo, "app.py", "two\n")
        record = os.path.join(sh(repo, "rev-parse", "--absolute-git-dir"), review_scope.RECORD)
        with open(record, "w", encoding="utf-8") as handle:
            handle.write("not json")
        got = verdicts(repo)
        check("an unreadable record covers nothing", got["clean-code"], "RUN (1 code file(s) changed)")

        write(repo, "docs/shot.png", "png\n")
        polish(repo)
        got = verdicts(repo)
        check("screenshots are checked over a polished tree when the docs hold images", (got["clean-code"], got["screenshot-relevance"]), ("SKIP (review-auto polished this tree)", "RUN (code changed, so prose about it may be stale)"))
        write(repo, "docs/raw/shot.png", "png\n")
        os.remove(os.path.join(repo, "docs", "shot.png"))
        check("an image under raw/ is not documentation", verdicts(repo)["screenshot-relevance"], "SKIP (the docs hold no images)")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    for line in failures:
        print(line)
    print(f"change-scope tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
