#!/usr/bin/env python3
"""What a repo has said it does and does not do, read one way for every skill that asks.

    repo_flags.py get <repo-root> <KEY>           yes or no, or nothing when the repo has not said
    repo_flags.py set <repo-root> <KEY> <yes|no>  record an answer, replacing any earlier one for KEY

The answers live in a committed `.claude/repo-flags`, one `KEY=value` per line, `#` starting a comment.
What a key the file does not name means is stated per key in `KEYS`: either the skill's old default, or that
the skill asks the user which value to record.

Every read validates the whole file and exits 2 naming the line on an unknown key, a value other than
yes or no, or a line that is not `KEY=value`. A misspelt key that read as unset would switch nothing
off and say nothing, which is the failure an opt-out exists to prevent.

A key belongs in `KEYS` only once a skill reads it, and the reader is named beside it.
"""

from __future__ import annotations

import os
import re
import sys

# The one "is this path ignored, and by which rule" probe; realpath, since ~/.claude/skills is a link.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "conventions", "rules"))
from _git import GitRefused, git, ignored, rules_for  # noqa: E402 — needs the sys.path line above

REL = ".claude/repo-flags"
VALUES = ("yes", "no")

# key -> (what an unset key means, what the key decides, who reads it)
KEYS = {
    "RELEASES": ("releases are offered", "no: the repo is never released, so /wrap-up makes no release offer",
                 "wrap-up/scripts/release_candidates.sh"),
    "SCREENSHOTS": ("the user is asked which value to record",
                    "yes: the docs keep screenshots and every screenshot pass runs, private repo or not; "
                    "no: none is checked, captured or offered",
                    "shared/change_scope.py, wrap-up, screenshot-relevance, docs-screenshot"),
}

LINE_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


class FlagsError(Exception):
    """The file holds something no reader can act on."""


def _path_of(root: str) -> str:
    return os.path.join(root, *REL.split("/"))


def _read_lines(root: str) -> list[str]:
    try:
        with open(_path_of(root), encoding="utf-8-sig", newline="") as handle:
            return [line.rstrip("\n").replace("\r", "") for line in handle]
    except FileNotFoundError:
        return []


def _parse(lines: list[str]) -> dict[str, str]:
    """Every answer in the file, raising on the first line that is not a known key with yes or no."""
    found: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        match = LINE_RE.match(text)
        if not match:
            raise FlagsError(f"{REL}:{number}: `{line}` is not KEY=value")
        key, value = match.group(1), match.group(2).strip()
        if key not in KEYS:
            raise FlagsError(f"{REL}:{number}: unknown key {key}; known: {', '.join(sorted(KEYS))}")
        if value not in VALUES:
            raise FlagsError(f"{REL}:{number}: {key}={value} is neither yes nor no")
        if key in found:
            raise FlagsError(f"{REL}:{number}: {key} is set a second time")
        found[key] = value
    return found


def _known(key: str) -> None:
    if key not in KEYS:
        raise FlagsError(f"unknown key {key}; known: {', '.join(sorted(KEYS))}")


def get(root: str, key: str) -> str:
    """The repo's answer for `key`, or "" when it has not given one."""
    _known(key)
    return _parse(_read_lines(root)).get(key, "")


def _refuse_if_ignored(root: str) -> None:
    """Raise when git would never stage the file, which makes the answer exist on this machine alone.

    A repo that allowlists `.claude/` (`.claude/*` with named exceptions) hides the file without a word,
    and every reader here still finds it, so the flag looks recorded until the other clone asks again.
    The verdict and the rule's name come from `ignored` and `rules_for` in conventions/rules/_git.py.
    Outside a git work tree there is nothing to stage and nothing to refuse; a repo git will not speak
    about at all (dubious ownership) reads the same way here, and git refuses its commit anyway.
    """
    try:
        inside = git(root, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return
        if not ignored(root, [REL]):
            return
        rule = rules_for(root, [REL]).get(REL)
    except GitRefused as exc:
        raise FlagsError(f"whether git ignores {REL} is unknown, so nothing was written: {exc}") from exc
    named = f"{rule.source}:{rule.line_no}:{rule.pattern}" if rule else "an ignore rule"
    raise FlagsError(f"{REL} is ignored by {named}, so it would never be committed; "
                     f"un-ignore it (an allowlisting .gitignore needs `!{REL}`) and set it again")


def set_flag(root: str, key: str, value: str) -> None:
    """Record `key=value`, replacing an earlier line for the key in place and keeping every other line."""
    _known(key)
    if value not in VALUES:
        raise FlagsError(f"{key}={value} is neither yes nor no")
    _refuse_if_ignored(root)
    lines = _read_lines(root)
    _parse(lines)
    entry = f"{key}={value}"
    for index, line in enumerate(lines):
        match = LINE_RE.match(line.split("#", 1)[0].strip())
        if match and match.group(1) == key:
            lines[index] = entry
            break
    else:
        lines.append(entry)
    os.makedirs(os.path.dirname(_path_of(root)), exist_ok=True)
    with open(_path_of(root), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 3 and argv[0] == "get":
            print(get(argv[1], argv[2]))
            return 0
        if len(argv) == 4 and argv[0] == "set":
            set_flag(argv[1], argv[2], argv[3])
            return 0
    except FlagsError as exc:
        print(f"repo_flags: {exc}", file=sys.stderr)
        return 2
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
