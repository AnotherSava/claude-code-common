"""A tray icon's left click reaches the app that drew it, rather than opening the menu macOS shows.

On macOS 27 a status item that keeps a menu attached loses its left click to that menu. The OS
presents the menu, the overlay view tray-icon installs never receives the press, and the app's own
left-click handler never runs — so `show_menu_on_left_click(false)` has no effect, and a widget
whose icon is meant to show and hide a window shows a menu instead. Nothing in the app's own source
explains it, which is what makes the version the thing to assert: the dashboard's `tray.rs` passes
that flag and reads correctly, and the diagnosis on 2026-10-04 ended in the dependency.

tray-icon 0.25.1 attaches the menu only while it is being presented (tauri-apps/tray-icon#365, which
closed tauri-apps/tray-icon#355). No call anywhere in a repo distinguishes a build that behaves from
one that does not, so a floor on the locked version is the only readable form of the property.

The floor names tray-icon rather than tauri, which is what a project actually declares. tauri 2.11.5
requires `tray-icon = "0.24"` and 2.12.1 requires `"0.25"`, so a tauri-keyed floor would say the
right thing only until that requirement moves again, and a version folder is frozen once any repo
has run it. The narrower subject also scopes itself: tauri's tray-icon dependency is optional, so a
Tauri app built without a tray locks no copy of it and this rule holds with nothing to say.

`Cargo.lock` is where the question is answered. A manifest declares a range; the lock records what a
build links, and under a range like `tauri = "2"` the manifest names no tray-icon version at all.
Which locks count is git's answer rather than a name list — the walk prunes the directories git
hides and what survives is narrowed again to the paths git hides individually, so a lock under
`target/` or inside a scratch clone is not read as a project's, while one force-added inside an
ignored directory still counts.

The file is read as lines rather than parsed as TOML, and what makes a line scan safe is that it
refuses. A `[[package]]` block with no name or no version, a line inside one this reader cannot
classify, and a version string that is not semver are each raised with the file and the line
verbatim, because which crate version a build links is not a guess this rule gets to make.
"""

from __future__ import annotations

import os
import re
from typing import NamedTuple

import _git

LOCK = "Cargo.lock"
CRATE = "tray-icon"
# Where tauri-apps/tray-icon#365 shipped. The number is a floor and never a currency claim: it marks
# where one defect was fixed, so it does not move when the crate releases again, and a rule keyed on
# the newest version would fail every conforming repo the morning upstream published.
FLOOR = (0, 25, 1)
FLOOR_TEXT = "0.25.1"
# The tauri release whose own requirement first admits that floor, for the message a finding prints.
VIA_TAURI = "2.12.1"

PACKAGE_TABLE = "[[package]]"
# A table header of either form. `[[patch.unused]]` and `[metadata]` both end a package block, and
# neither is one.
TABLE_RE = re.compile(r"^\[\[?[^\[\]]+\]\]?$")
STRING_RE = re.compile(r'^([A-Za-z0-9_-]+)\s*=\s*"([^"]*)"$')
# A quoted key, which a lock in cargo's first format uses throughout its `[metadata]` table
# (`"checksum adler32 1.0.4 (registry+…)" = "5d2e…"`). Classified rather than refused: it is a legal
# TOML key and a shape cargo really writes, while `name` and `version` are always written bare, so
# nothing this rule reads can arrive in it.
QUOTED_KEY_RE = re.compile(r'^"[^"]*"\s*=\s*.+$')
BARE_RE = re.compile(r'^([A-Za-z0-9_-]+)\s*=\s*(?:\d+|true|false)$')
ARRAY_INLINE_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*=\s*\[.*\]$")
ARRAY_OPEN_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*=\s*\[$")
ARRAY_ITEM_RE = re.compile(r'^"[^"]*",?$')
ARRAY_CLOSE = "]"
# A version with an optional prerelease tag and optional build metadata, the three forms cargo
# writes into a lock.
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")


class Unreadable(Exception):
    """A lock that is there and would not read, so what it links was never established.

    Raised rather than returned, for `_git.GitRefused`'s reason: a rule holding a reason string can
    drop it, and a dropped reason becomes a pass.
    """


class Package(NamedTuple):
    name: str
    version: str
    line: int  # where the block's own `[[package]]` header sits, which is what a reader scrolls to


def locks(root: str) -> list[str]:
    """Every Cargo.lock in `root` that a person maintains, repo-relative and sorted."""
    try:
        hidden_dirs = {entry.rstrip("/") for entry in _git.ignored_on_disk(root) if entry.endswith("/")}
    except _git.GitRefused as exc:
        raise _git.GitRefused(f"{exc}, so which directories here hold a project's {LOCK} rather than a "
                              f"build's could not be established") from exc
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        rel = os.path.relpath(base, root).replace(os.sep, "/")
        prefix = "" if rel == "." else f"{rel}/"
        dirs[:] = sorted(name for name in dirs
                         if name != ".git" and f"{prefix}{name}" not in hidden_dirs)
        if LOCK in files:
            found.append(f"{prefix}{LOCK}")
    try:
        hidden = _git.ignored_untracked(root, found)
    except _git.GitRefused as exc:
        raise _git.GitRefused(f"{exc}, so which of the {len(found)} {LOCK} file(s) here are a project's "
                              f"could not be established") from exc
    return sorted(set(found) - hidden)


def read_lines(root: str, rel: str) -> list[str]:
    """A lock's lines. Raises when the file is there and will not open."""
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as handle:
            return handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{rel} is on disk and would not open ({exc}), so the crate versions it locks "
                         f"were never read") from exc


def packages(rel: str, lines: list[str]) -> list[Package]:
    """Every `[[package]]` block in one lock, as its name and version.

    Stops on anything it cannot classify. A reader that skipped an unrecognized line would be
    verifying the shapes it already knew about, which is the parser whose verification is scoped to
    its own blind spots.
    """
    found: list[Package] = []
    name = version = ""
    header = 0
    in_package = False
    in_array = False

    def close() -> None:
        nonlocal name, version
        if not in_package:
            return
        if not name or not version:
            missing = "no name" if not name else "no version"
            raise Unreadable(f"{rel} line {header}: a {PACKAGE_TABLE} block carries {missing}, so which "
                             f"crate it locks is unknown")
        found.append(Package(name, version, header))
        name = version = ""

    for number, text in enumerate(lines, 1):
        bare = text.strip()
        if in_array:
            if bare == ARRAY_CLOSE:
                in_array = False
            elif not ARRAY_ITEM_RE.match(bare):
                raise Unreadable(f"{rel} line {number}: inside an array this reader cannot classify — "
                                 f"{text!r}")
            continue
        if not bare or bare.startswith("#"):
            continue
        if TABLE_RE.match(bare):
            close()
            in_package = bare == PACKAGE_TABLE
            header = number
            continue
        if ARRAY_OPEN_RE.match(bare):
            in_array = True
            continue
        if ARRAY_INLINE_RE.match(bare) or BARE_RE.match(bare) or QUOTED_KEY_RE.match(bare):
            continue
        string = STRING_RE.match(bare)
        if string is None:
            raise Unreadable(f"{rel} line {number}: a line this reader cannot classify — {text!r}")
        if in_package and string.group(1) == "name":
            name = string.group(2)
        elif in_package and string.group(1) == "version":
            version = string.group(2)
    if in_array:
        raise Unreadable(f"{rel} ends inside an unclosed array, so the blocks after it were never read")
    close()
    return found


def below_floor(rel: str, package: Package) -> bool:
    """Whether this locked version precedes the release that fixed the click.

    A prerelease of the floor itself precedes it — `0.25.1-rc.1` is not `0.25.1` — while a
    prerelease of any later version follows, so only the equal case consults the tag.
    """
    match = VERSION_RE.match(package.version)
    if match is None:
        raise Unreadable(f"{rel} line {package.line}: {CRATE} is locked at {package.version!r}, which this "
                         f"rule cannot read as a version, so whether it precedes {FLOOR_TEXT} is unknown")
    trio = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if trio != FLOOR:
        return trio < FLOOR
    return match.group(4) is not None


def check(root: str) -> list[str]:
    """One line per locked tray-icon that precedes the fix, empty when every lock is at or above it."""
    violations: list[str] = []
    for rel in locks(root):
        for package in packages(rel, read_lines(root, rel)):
            if package.name != CRATE or not below_floor(rel, package):
                continue
            violations.append(
                f"{rel} line {package.line}: {CRATE} is locked at {package.version}, which keeps its menu "
                f"attached to the status item for the item's whole life — on macOS 27 the OS takes a left "
                f"click for that menu, so this build's own left-click handler never runs however it is "
                f"configured. {FLOOR_TEXT} or newer is the fix, reachable under tauri {VIA_TAURI} or newer")
    return violations
