"""Scratch-repo scaffolding the git-driving test suites share: the sealed git config, the `git -C` runner, the
`check` that collects failures, and the `report` that ends a suite; and `find_bash`, which the suites here that
spawn bash resolve it through.

One module because every suite here that runs git for real owes the same seal, and a fix made to one copy of it (a
new config key, a timeout) would leave the others reading this machine's config, signing key included. A suite that
runs no git imports only what it needs of `check`, `report` and `find_bash`, none of which touches git or the
environment until a seal is asked for.

Git writes loose objects and packs read-only, which Windows refuses to delete, so a scratch repo that holds any goes
in a `tempfile.TemporaryDirectory`: its exit makes such a file writable and deletes it again, raising if that fails
too. On Windows, a `mkdtemp` removed with `shutil.rmtree(..., ignore_errors=True)` leaves those files and every
directory above them in the temp directory on every run, with nothing reporting it.
"""

from __future__ import annotations

import os
import shutil
import subprocess

_failures: list[str] = []
uncovered: list[str] = []

SEALED_CONFIG = "[user]\n\tname = t\n\temail = t@example.invalid\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n"


def seal(scratch: str, extra_config: str = "") -> dict[str, str | None]:
    """Point every git this process starts at a config written under `scratch`, and at no system config.

    -> what the two variables held before, for a suite that has to hand one step this machine's own config back.
    """
    path = os.path.join(scratch, "gitconfig")
    before = {name: os.environ.get(name) for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
    os.environ.update({"GIT_CONFIG_GLOBAL": path, "GIT_CONFIG_NOSYSTEM": "1"})
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(SEALED_CONFIG + extra_config)
    return before


def find_bash(suite: str) -> str | None:
    """The path of the bash on PATH, or None after printing `suite`'s NOT COVERED line when no bash is on PATH.

    A bare "bash" handed to CreateProcess finds System32's WSL launcher before Git Bash on PATH; spawning which()'s
    result never reaches System32. learnings/windows-spawning-bash.md. The gate script resolves bash the same way in
    its own `_find_bash`, skills/shared/gate_pushed_tree.py, which sits outside this test directory.
    """
    bash = shutil.which("bash")
    if not bash:
        print(f"{suite}: NOT COVERED — no bash on PATH")
    return bash


def check(label: str, got: object, want: object) -> None:
    if got != want:
        _failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def report(suite: str) -> int:
    """Print the NOT COVERED lines, any failures, and the summary line; return the suite's exit code.

    The commit gate shows only a passing suite's last line, so the NOT COVERED count and the first reason go in it.
    """
    for line in uncovered:
        print(f"  NOT COVERED {line}")
    missing = f", {len(uncovered)} NOT COVERED — {uncovered[0]}" if uncovered else ""
    if _failures:
        print("\n".join(_failures))
        print(f"{suite}: {len(_failures)} failure(s){missing}")
        return 1
    print(f"{suite}: all cases behave{missing}")
    return 0


def sh(repo: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def write(repo: str, name: str, text: str) -> None:
    path = os.path.join(repo, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def commit(repo: str, name: str, text: str) -> str:
    """Write `name`, commit everything as `edit <name>`, and return the new commit's sha."""
    write(repo, name, text)
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", f"edit {name}")
    return sh(repo, "rev-parse", "HEAD")
