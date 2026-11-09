"""Scratch-repo scaffolding the git-driving test suites share: the sealed git config, the `git -C` runner, the
`check` that collects failures, and the `report` that ends a suite.

One module because every suite here that runs git for real owes the same seal, and a fix made to one copy of it (a
new config key, a timeout) would leave the others reading this machine's config, signing key included. A suite that
runs no git imports `check` and `report` alone, which touch nothing until a seal is asked for.
"""

from __future__ import annotations

import os
import subprocess

_failures: list[str] = []
uncovered: list[str] = []

SEALED_CONFIG = "[user]\n\tname = t\n\temail = t@example.invalid\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n"


def seal(scratch: str, extra_config: str = "") -> None:
    """Point every git this process starts at a config written under `scratch`, and at no system config."""
    path = os.path.join(scratch, "gitconfig")
    os.environ.update({"GIT_CONFIG_GLOBAL": path, "GIT_CONFIG_NOSYSTEM": "1"})
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(SEALED_CONFIG + extra_config)


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
