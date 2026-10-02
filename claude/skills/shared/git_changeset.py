#!/usr/bin/env python3
"""Reading a repository's pending change set, shared by the tools that act on one.

The porcelain parse below is the reason this module exists rather than being copied: it has an
offset trap, a rename trap and a non-ASCII trap, all three documented in
`~/.claude/learnings/git-porcelain-parsing.md`. A second copy is a second place for the next
correction to miss.

Not a CLI — import it:

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
    from git_changeset import changed_paths, git
"""

from __future__ import annotations

import os
import subprocess

PATHSPEC_MAGIC = ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")


def git(args: list[str], cwd: str | None = None, binary: bool = False) -> bytes | str:
    """Run git with pathspec magic neutralised.

    A caller's environment can switch pathspec magic off — Magit exports `GIT_LITERAL_PATHSPECS`
    to every child — and under it a `:(attr:…)` or `:(glob)` pathspec matches nothing while the
    command still exits 0. Any selection built on magic then passes everything, silently.
    """
    env = dict(os.environ)
    for magic in PATHSPEC_MAGIC:
        env.pop(magic, None)
    done = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, check=True, env=env)
    return done.stdout if binary else done.stdout.decode("utf-8", "surrogateescape")


def changed_paths(cwd: str | None = None, untracked: bool = True) -> list[str]:
    """Every path in the working tree's change set, both halves of a rename, ignored files excluded.

    `-z` is what makes this safe to parse: without it git escapes non-ASCII bytes and quotes the
    result, so a Cyrillic or CJK filename comes back as octal escapes and compares unequal to the
    name on disk. A rename or copy entry spends two NUL-separated fields — destination then source.
    A rename's source is a path the change set removes, so it is returned too: a caller that copies
    present paths and deletes absent ones would otherwise keep the old file alongside the new one.
    A copy's source is unchanged and is skipped.
    """
    args = ["status", "--porcelain", "-z"] + (["-uall"] if untracked else ["-uno"])
    fields = git(args, cwd=cwd, binary=True).split(b"\0")
    paths: list[str] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        code = entry[:2].decode("ascii", "replace")
        paths.append(entry[3:].decode("utf-8", "surrogateescape"))
        if "R" in code and i + 1 < len(fields):
            paths.append(fields[i + 1].decode("utf-8", "surrogateescape"))
        i += 2 if ("R" in code or "C" in code) else 1
    return paths
