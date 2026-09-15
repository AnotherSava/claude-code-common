"""Which package.json files in a repo are a project's, and how to write one key into one.

The three Node steps — v7 engines, v8 engine-strict, v9 packageManager — all answer the
same question before they do anything, and they have to answer it identically. A repo
whose app lives under `web/` carries `web/.next/package.json` and one package.json per
installed dependency under `web/node_modules/`; a plain `find` returns all of them, and a
step that wrote a pin into one of those would be writing into a tree the next build
replaces. Worse, the three steps disagreeing about the set is a repo that passes v7 and
then has v8 assert against manifests v7 never looked at.

So the set is derived once, here, by walking the tree and never descending into a
directory a build tool owns. Everything a caller gets back is repo-relative with forward
slashes, so a path reads and records the same on both machines.

**This module is frozen surface, exactly as the step scripts that import it are, from the
moment the first repo records a line for v7, v8 or v9.** A change to what `manifests`
returns after that retroactively changes what those steps asserted wherever an `applied`
line already stands, which is the thing `references/authoring-a-step.md` forbids: a shipped
step is corrected by a new step carrying `supersedes:`, never by an edit. Read a bug found
after that point as a reason to write the next step, not to edit this one.
"""

import json
import os
from typing import NamedTuple

import _own_fixtures

# Directories a build tool, a package manager or a language toolchain owns. A package.json
# below one of these is generated output, a vendored copy, or an installed dependency —
# never a manifest anybody edits. The first four are the set the fleet survey measured
# (`web/.next/standalone/package.json` is the case that named this list); the rest are the
# same shape from the other toolchains these repos use, listed so a repo that gains one
# later does not quietly start reporting a build artefact as a project.
GENERATED = (".angular", ".cache", ".git", ".next", ".nuxt", ".output", ".parcel-cache",
             ".pnpm-store", ".svelte-kit", ".turbo", ".venv", ".vercel", ".yarn", "bower_components",
             "build", "coverage", "dist", "node_modules", "out", "storybook-static", "target", "vendor")


class Manifest(NamedTuple):
    rel: str        # repo-relative, forward slashes
    raw: str        # the file's text, untranslated, so a rewrite preserves its line endings
    data: dict      # the parsed object, empty when `error` is set
    error: str      # why it could not be read at all; a step reports this and stops


def manifests(root: str) -> list[str]:
    """Every package.json in `root` that a person maintains, repo-relative and sorted."""
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        kept = sorted(name for name in dirs if name not in GENERATED)
        dirs[:] = _own_fixtures.prune(base, kept)
        if "package.json" in files:
            found.append(os.path.relpath(os.path.join(base, "package.json"), root).replace(os.sep, "/"))
    return sorted(found)


def read(root: str, rel: str) -> Manifest:
    """One manifest, with the reason it could not be read rather than an exception.

    Read with `newline=""` so the text comes back exactly as stored: a file committed with
    CRLF must not become a whole-file line-ending diff just because a step added one key to
    it, and these repos are worked on from a Windows machine as well as this one.
    """
    path = os.path.join(root, *rel.split("/"))
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        return Manifest(rel, "", {}, f"{rel} could not be read ({exc})")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return Manifest(rel, raw, {}, f"{rel} is not valid JSON ({exc})")
    if not isinstance(data, dict):
        return Manifest(rel, raw, {}, f"{rel} does not hold a JSON object at its top level")
    return Manifest(rel, raw, data, "")


def read_all(root: str) -> list[Manifest]:
    """Every project manifest, read. A caller checks `error` before trusting `data`."""
    return [read(root, rel) for rel in manifests(root)]


def sibling(rel: str, name: str) -> str:
    """The repo-relative path of `name` beside a manifest — its `.nvmrc`, its `.npmrc`.

    Beside, and never above: npm resolves the project config from the directory holding
    package.json, so an `.npmrc` at a repo root is not read at all when npm runs in `web/`.
    """
    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    return f"{parent}/{name}" if parent else name


def read_text(root: str, rel: str) -> str | None:
    """A sibling file's text, or None when it is not there or cannot be read."""
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def newline_of(raw: str) -> str:
    """The line ending already in this file, so an inserted line matches its neighbours."""
    return "\r\n" if "\r\n" in raw else "\n"


def write_atomic(path: str, text: str) -> str:
    """Replace a file's content in one step, or leave the original exactly as it was.

    Written through a temporary beside it and `os.replace`, which is atomic on both
    platforms: a step interrupted mid-write must never leave a committed package.json
    truncated, and idempotence rule 2 is that every source artifact survives every failure.
    `newline=""` writes the text through untouched — the translation rule 4 exists to stop
    is Python turning "\\n" into "\\r\\n" on Windows, and passing the file's own endings
    back is the same guarantee without rewriting a file nobody asked to reformat.
    """
    temporary = f"{path}.adopt-tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            os.remove(temporary)
        except OSError:
            pass
        return f"could not be written ({exc})"
    return ""


def _end_of_string(raw: str, start: int) -> int | None:
    """Index just past the closing quote of the JSON string opening at `start`."""
    index = start + 1
    while index < len(raw):
        if raw[index] == "\\":
            index += 2
            continue
        if raw[index] == '"':
            return index + 1
        index += 1
    return None


def _end_of_value(raw: str, start: int) -> int | None:
    """Index just past the value beginning at or after `start`, whatever kind it is."""
    index = start
    while index < len(raw) and raw[index] in " \t\r\n":
        index += 1
    if index >= len(raw):
        return None
    if raw[index] == '"':
        return _end_of_string(raw, index)
    if raw[index] in "{[":
        depth = 0
        while index < len(raw):
            char = raw[index]
            if char == '"':
                closed = _end_of_string(raw, index)
                if closed is None:
                    return None
                index = closed
                continue
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
        return None
    primitive = index
    while index < len(raw) and raw[index] not in ",}]":
        index += 1
    # Back off the whitespace between the value and whatever ends it. Without this the scan for a
    # primitive runs up to the closing brace and swallows the newline before it, so a key appended
    # after the file's last one is written as `true\n,\n  "engines": {…}}` — the comma orphaned on
    # its own line and the closing brace glued to the inserted value. It parses, so `json.loads`
    # and the read-back assertion both pass and the reformat ships.
    while index > primitive and raw[index - 1] in " \t\r\n":
        index -= 1
    return index


def top_level_keys(raw: str) -> list[tuple[str, int, int]] | None:
    """(name, offset of its opening quote, offset just past its value) per top-level key.

    None means the text is not a shape this reader will edit. Refusing is the point: the
    alternative is a regex that matches a nested `"scripts"` as readily as the real one and
    inserts a key inside `devDependencies`, and a step that cannot read a file must abort
    rather than guess at it (idempotence rule 6).
    """
    start = raw.find("{")
    if start < 0:
        return None
    index, found = start + 1, []
    while index < len(raw):
        char = raw[index]
        if char in " \t\r\n,":
            index += 1
            continue
        if char == "}":
            return found
        if char != '"':
            return None
        key_end = _end_of_string(raw, index)
        if key_end is None:
            return None
        try:
            name = json.loads(raw[index:key_end])
        except ValueError:
            return None
        key_start, index = index, key_end
        while index < len(raw) and raw[index] in " \t\r\n":
            index += 1
        if index >= len(raw) or raw[index] != ":":
            return None
        value_end = _end_of_value(raw, index + 1)
        if value_end is None:
            return None
        found.append((name, key_start, value_end))
        index = value_end
    return None


def _indent_of(raw: str, offset: int) -> str:
    line_start = raw.rfind("\n", 0, offset) + 1
    lead = raw[line_start:offset]
    return lead if lead.strip() == "" else "  "


def key_indent(raw: str) -> str:
    """The indent this file already puts its top-level keys at, for a value written over lines.

    A caller adding an object-valued key needs it: writing `{"node": ">=24 <25"}` on one line
    into a file whose every other object is expanded makes the added key the odd one out, and
    the point of inserting textually rather than re-dumping is that the result reads like the
    rest of the file.
    """
    keys = top_level_keys(raw)
    return _indent_of(raw, keys[0][1]) if keys else "  "


def insert_key(raw: str, key: str, literal: str, before: tuple[str, ...]) -> str | None:
    """`raw` with one top-level key added, placed before the first of `before` present.

    Everything else in the file is copied byte for byte, so the change reads as one added
    line rather than as a reformat: a whole-file diff on a committed manifest hides the one
    line that actually changed, and these repos are reviewed by eye before every commit.
    Returns None when the file's shape could not be read or already holds the key.
    """
    keys = top_level_keys(raw)
    if not keys or any(name == key for name, _, _ in keys):
        return None
    line_end = newline_of(raw)
    indent = _indent_of(raw, keys[0][1])
    for name, key_start, _ in keys:
        if name in before:
            return f"{raw[:key_start]}\"{key}\": {literal},{line_end}{indent}{raw[key_start:]}"
    _, _, last_end = keys[-1]
    return f"{raw[:last_end]},{line_end}{indent}\"{key}\": {literal}{raw[last_end:]}"
