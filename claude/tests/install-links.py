#!/usr/bin/env python3
"""The install blocks in README.md and check-install.py's lists say the same thing.

Three copies of one contract have to agree: the PowerShell block a Windows machine is installed
from, the bash block a macOS one is installed from, and the `LINKS` / `GIT_SETTINGS` lists the
session-start check verifies against. Nothing made them agree, and the gap is silent in the way
that matters — an install block is read once per machine, years apart, while the check quietly
never looks at what it was not told about.

Measured, 2026-09-16: `~/.claude/conventions` had been in both install blocks and in no list, so it
existed on neither machine and nothing said so. Every documented `check.py` and `engine.py` command
failed on both, the commit gate of any repo that adopted the version requiring it would have failed
too, and `check-install.py` reported a clean install throughout.

What is asserted, all of it both ways:

  the two blocks         the same links and the same git settings, since a link added to one and
                         not the other installs a machine that is correct on one platform only
  blocks vs LINKS        every documented link is checked, and every checked link is documented
  git settings           each one's value resolves, through the links the blocks create, to the
                         repo path `GIT_SETTINGS` expects — `core.hooksPath` pointing at
                         `~/.git-hooks` is only right because that link goes to `git/hooks`

A line inside either block that this file cannot classify stops the run rather than being skipped.
A parser that skips is a parser whose verification is scoped to its own blind spots: a mistyped
`New-Item` would otherwise drop a link out of the comparison and read as agreement.

Usage:  python claude/tests/install-links.py
Exit:   0 the three copies agree, 1 they do not or a line could not be read
"""

import importlib.util
import os
import re
import sys
from types import ModuleType

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
README = os.path.join(REPO, "README.md")
CHECK_INSTALL = os.path.join(REPO, "claude", "hooks", "check-install.py")

WINDOWS_HEADING = "### Windows"
UNIX_HEADING = "### Linux / macOS"

NEW_ITEM_RE = re.compile(r'^New-Item -ItemType SymbolicLink -Path "([^"]+)" -Target "([^"]+)"$')
LN_RE = re.compile(r'^ln -s "([^"]+)" (\S+)$')
GIT_CONFIG_RE = re.compile(r'^git config --global (\S+) "?([^"]+?)"?$')
# Lines that carry no link and are still expected: each block creates the directory the links go
# into. Listed rather than pattern-matched, so a new one is a stop rather than a silent skip.
IGNORED = ("mkdir -p ~/.claude",
           'New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\\.claude" | Out-Null')

FAILURES: list[str] = []


class Unreadable(Exception):
    """A line, or a block, this file will not guess at."""


def fail(message: str) -> None:
    FAILURES.append(message)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def block_after(text: str, heading: str) -> list[str]:
    """The first fenced code block under `heading`, as its lines.

    Scoped by heading rather than by fence language, because the same section holds a second bash
    block — the one that runs the check by hand — and comparing that one against the install lists
    would report every link as undocumented.
    """
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        raise Unreadable(f"README.md has no {heading!r} section, so there is no install block to read") from None
    opened = False
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("```"):
            if opened:
                return body
            opened = True
            continue
        if opened:
            body.append(line)
    raise Unreadable(f"the code block under {heading!r} in README.md is never closed")


def home_path(raw: str) -> str:
    """A link path as the lists spell it: `~/…`, forward slashes."""
    text = raw.replace("\\", "/")
    for prefix in ("$env:USERPROFILE/", "$HOME/", "~/"):
        if text.startswith(prefix):
            return "~/" + text[len(prefix):]
    raise Unreadable(f"{raw!r} names no path under the home directory, which is where every link goes")


def repo_path(raw: str) -> str:
    """A target as the lists spell it: repo-relative, forward slashes."""
    text = raw.replace("\\", "/")
    for prefix in ("$PWD/", "$(pwd)/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    raise Unreadable(f"{raw!r} is not written relative to the checkout, so which file it links to is unknown")


def parse_block(lines: list[str], where: str) -> tuple[dict[str, str], dict[str, str]]:
    """-> ({link: repo path}, {git setting: its value}) for one install block."""
    links: dict[str, str] = {}
    settings: dict[str, str] = {}
    for line in lines:
        text = line.strip()
        if not text or text in IGNORED:
            continue
        new_item = NEW_ITEM_RE.match(text)
        link = LN_RE.match(text)
        setting = GIT_CONFIG_RE.match(text)
        if new_item:
            links[home_path(new_item.group(1))] = repo_path(new_item.group(2))
        elif link:
            links[home_path(link.group(2))] = repo_path(link.group(1))
        elif setting:
            settings[setting.group(1)] = home_path(setting.group(2))
        else:
            raise Unreadable(f"the {where} install block holds a line this check cannot classify: {text!r}")
    if not links:
        raise Unreadable(f"the {where} install block creates no links at all, which cannot be right")
    return links, settings


def load_check_install() -> ModuleType:
    """check-install.py as a module. Importing it runs no checks — its work is behind a main guard."""
    spec = importlib.util.spec_from_file_location("check_install", CHECK_INSTALL)
    if spec is None or spec.loader is None:
        raise Unreadable(f"{CHECK_INSTALL} could not be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_install"] = module
    spec.loader.exec_module(module)
    return module


def compare(label: str, left: dict[str, str], right: dict[str, str], left_name: str, right_name: str) -> None:
    """Report every disagreement between two mappings, named from both sides."""
    for key in sorted(set(left) - set(right)):
        fail(f"{label}: {key} is in {left_name} and not in {right_name}")
    for key in sorted(set(right) - set(left)):
        fail(f"{label}: {key} is in {right_name} and not in {left_name}")
    for key in sorted(set(left) & set(right)):
        if left[key] != right[key]:
            fail(f"{label}: {key} points at {left[key]} in {left_name} and {right[key]} in {right_name}")


def main() -> int:
    try:
        readme = read_text(README)
        windows_links, windows_settings = parse_block(block_after(readme, WINDOWS_HEADING), "Windows")
        unix_links, unix_settings = parse_block(block_after(readme, UNIX_HEADING), "Linux / macOS")
        module = load_check_install()
    except (Unreadable, OSError, UnicodeDecodeError) as exc:
        # Not a failure count: nothing was compared, and a run that could not read its inputs must
        # not report the same "all agree" a clean run does.
        print(f"install links: NOT CHECKED — {exc}")
        return 1

    compare("the two install blocks", windows_links, unix_links, "the Windows block", "the Linux / macOS block")
    compare("the two install blocks", windows_settings, unix_settings, "the Windows block", "the Linux / macOS block")
    compare("README against check-install.py", windows_links, dict(module.LINKS),
            "the install blocks", "the LINKS list")

    # A git setting names a path rather than a repo file, so it is read through the links the blocks
    # just created: `core.hooksPath = ~/.git-hooks` is correct only while that link goes to git/hooks.
    expected = dict(module.GIT_SETTINGS)
    for key in sorted(set(expected) - set(windows_settings)):
        fail(f"git settings: {key} is verified by check-install.py and set by neither install block")
    for key in sorted(set(windows_settings) - set(expected)):
        fail(f"git settings: {key} is set by the install blocks and verified by nothing")
    for key in sorted(set(expected) & set(windows_settings)):
        target = windows_links.get(windows_settings[key])
        if target is None:
            fail(f"git settings: {key} is set to {windows_settings[key]}, which the install blocks never link")
        elif target != expected[key]:
            fail(f"git settings: {key} reaches {target} through the links, and check-install.py "
                 f"expects {expected[key]}")

    if FAILURES:
        print(f"install links: {len(FAILURES)} disagreement(s) between README.md and check-install.py\n")
        for failure in FAILURES:
            print(f"  {failure}")
        print()
        return 1
    print(f"install links: {len(windows_links)} link(s) and {len(windows_settings)} git setting(s) agree "
          f"across both install blocks and check-install.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
