#!/usr/bin/env python3
"""Cases for `claude/scripts/worktree-sandbox.py`.

The sandbox is what a sub-skill reviews instead of the user's tree, so a change set it fails to
carry in is a review that reports success over files it never saw — the failure that looks like a
pass. Each case below is one shape the carry-in has to get right, and the last two are the ones
that cost real time to discover: an ignored blob must stay out, and the sandbox must never land
inside the repo, where it would appear in the very change set being reviewed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "claude", "scripts", "worktree-sandbox.py")

failures: list[str] = []


def run(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def git(args: list[str], cwd: str) -> str:
    done = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def build_repo(root: str) -> None:
    git(["init", "-q", "."], root)
    git(["config", "user.email", "a@b.c"], root)
    git(["config", "user.name", "A"], root)
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "build"))
    write(root, "docs/page.md", "base\n")
    write(root, "keep.md", "keep\n")
    write(root, "docs/old.md", "moved\n")
    write(root, ".gitignore", "/build/\n")
    git(["add", "-A"], root)
    git(["commit", "-q", "--no-gpg-sign", "-m", "chore: base"], root)
    # The dirty state a review has to see: an edit, a new file, a deletion — plus an ignored blob
    # that must stay out, since carrying the working tree rather than the change set is what makes
    # this unusable on a repo whose bulk is build output.
    write(root, "docs/page.md", "base\nedited\n")
    write(root, "docs/new.md", "new\n")
    os.remove(os.path.join(root, "keep.md"))
    git(["mv", "docs/old.md", "docs/moved.md"], root)
    write(root, "build/blob", "x" * 200_000)


def write(root: str, rel: str, text: str) -> None:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)


def main() -> None:
    work = tempfile.mkdtemp(prefix="wt-sandbox-test-")
    repo = os.path.join(work, "repo")
    os.makedirs(repo)
    try:
        build_repo(repo)
        before = git(["status", "--porcelain"], repo)

        made = run([sys.executable, SCRIPT, "create", "--name", "probe"], repo)
        check("create exits 0", made.returncode, 0)
        sandbox = made.stdout.strip().split("\n")[-1] if made.returncode == 0 else ""
        if not sandbox or not os.path.isdir(sandbox):
            failures.append(f"  FAIL create produced no sandbox: {made.stdout!r} {made.stderr!r}")
            raise SystemExit(report())

        check("sandbox is outside the repo", os.path.commonpath([os.path.realpath(sandbox),
              os.path.realpath(repo)]) == os.path.realpath(repo), False)
        check("the edit arrived", open(os.path.join(sandbox, "docs/page.md")).read(), "base\nedited\n")
        check("the new file arrived", os.path.exists(os.path.join(sandbox, "docs/new.md")), True)
        check("the deletion arrived", os.path.exists(os.path.join(sandbox, "keep.md")), False)
        check("a staged rename's destination arrived", os.path.exists(os.path.join(sandbox, "docs/moved.md")), True)
        check("and its source is gone", os.path.exists(os.path.join(sandbox, "docs/old.md")), False)
        check("the ignored blob stayed out", os.path.exists(os.path.join(sandbox, "build/blob")), False)
        check("sandbox is clean after carry-in", git(["status", "--porcelain"], sandbox).strip(), "")
        check("the user's tree is untouched", git(["status", "--porcelain"], repo), before)

        # A sub-skill's edit must be the only thing the patch carries.
        write(sandbox, "docs/page.md", "base\nedited\nby the sub-skill\n")
        got = run([sys.executable, SCRIPT, "patch", sandbox], repo)
        check("patch exits 0", got.returncode, 0)
        check("patch names only the edited file", [l for l in got.stdout.split("\n") if l.startswith("+++")],
              ["+++ b/docs/page.md"])
        check("patch carries the sub-skill's line", "+by the sub-skill" in got.stdout, True)
        check("patch omits the carried-in change set", "+edited" in got.stdout, False)

        # The patch must apply to the user's tree, which is what makes the sandbox useful at all.
        patch_file = os.path.join(work, "p.diff")
        with open(patch_file, "w") as handle:
            handle.write(got.stdout)
        applied = run(["git", "apply", patch_file], repo)
        check("the patch applies to the real tree", applied.returncode, 0)
        check("and lands the sub-skill's line", "by the sub-skill" in open(os.path.join(repo, "docs/page.md")).read(), True)

        # An untracked file in the sandbox is absent from a plain diff; the tool must say so.
        write(sandbox, "docs/extra.md", "extra\n")
        noted = run([sys.executable, SCRIPT, "patch", sandbox], repo)
        check("untracked sandbox file is reported on stderr", "docs/extra.md" in noted.stderr, True)

        gone = run([sys.executable, SCRIPT, "remove", sandbox], repo)
        check("remove exits 0", gone.returncode, 0)
        check("sandbox is gone from disk", os.path.exists(sandbox), False)
        check("git no longer lists it", sandbox in git(["worktree", "list"], repo), False)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    raise SystemExit(report())


def report() -> int:
    for line in failures:
        print(line)
    print(f"worktree-sandbox tests: {'all cases behave' if not failures else f'{len(failures)} failure(s)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    main()
