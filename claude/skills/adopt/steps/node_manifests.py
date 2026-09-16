"""Which package.json files in a repo are a project's, and how to write one key into one.

The three Node steps — v7 engines, v8 engine-strict, v9 packageManager — all answer the
same question before they do anything, and they have to answer it identically. A repo
whose app lives under `web/` carries `web/.next/package.json` and one package.json per
installed dependency under `web/node_modules/`; a plain `find` returns all of them, and a
step that wrote a pin into one of those would be writing into a tree the next build
replaces. Worse, the three steps disagreeing about the set is a repo that passes v7 and
then has v8 assert against manifests v7 never looked at.

So the set is derived once, here, by two filters a caller never chooses between. The walk
never descends into a directory a build tool owns, and what survives it is then narrowed to
what git does not hide — a name rule cannot see a scratch clone, and the global convention
puts scratch in a gitignored `tmp/`, so a manifest inside one is a designed and recurring
condition rather than an accident. Everything a caller gets back is repo-relative with
forward slashes, so a path reads and records the same on both machines.

**This module is frozen surface, exactly as the step scripts that import it are, from the
moment the first repo records an `applied` line for v7, v8 or v9.** The condition is not
this file's to set, and it is worth reading it somewhere it cannot be rewritten to suit a
change somebody wants to make: `SKILL.md` gives the ban its reason — a shipped step "is
corrected by a new step carrying `supersedes:`, **because a repo already past that version
will never re-run it**". Past it is what does the work. An `n/a` line records the step
finding nothing to do, and a strictly smaller set still finds nothing, so narrowing cannot
retroactively change what such a repo asserted; an `applied` line is the one that can.

The git narrowing and `venv` below were added on 2026-09-15 under exactly that reading,
measured rather than assumed: of the user's 36 GitHub repositories exactly one carried a
committed `.claude/conventions.tsv` at all, holding v7, v8 and v9 as `n/a`, so no `applied`
line for these versions existed anywhere to falsify. Read the next bug found here as a
reason to write the next step rather than to edit this one — that measurement was the last
moment this route was open, and it is not re-openable by repeating it.
"""

import json
import os
from typing import NamedTuple

import _gitignore
import _own_fixtures

# Directories a build tool, a package manager or a language toolchain owns. A package.json
# below one of these is generated output, a vendored copy, or an installed dependency —
# never a manifest anybody edits. The first four are the set the fleet survey measured
# (`web/.next/standalone/package.json` is the case that named this list); the rest are the
# same shape from the other toolchains these repos use, listed so a repo that gains one
# later does not quietly start reporting a build artefact as a project.
#
# `.venv` and `venv` are both here because both are ordinary spellings and only the first was
# listed at first: two Python repos in the fleet were measured reading
# `venv/Lib/site-packages/playwright/driver/package/package.json` as a project of theirs, which
# declares `engines.node`, so v8's probe exited 0 in each and an approved walk would have written
# an `.npmrc` inside a virtualenv the next rebuild deletes.
GENERATED = (".angular", ".cache", ".git", ".next", ".nuxt", ".output", ".parcel-cache",
             ".pnpm-store", ".svelte-kit", ".turbo", ".venv", ".vercel", ".yarn", "bower_components",
             "build", "coverage", "dist", "node_modules", "out", "storybook-static", "target", "vendor",
             "venv")


class Manifest(NamedTuple):
    rel: str        # repo-relative, forward slashes
    raw: str        # the file's text, untranslated, so a rewrite preserves its line endings
    data: dict      # the parsed object, empty when `error` is set
    error: str      # why it could not be read at all; a step reports this and stops


class GitRefused(Exception):
    """Git would not say which paths it hides, so which manifests are a project's is unknown.

    Raised rather than swallowed, and never softened into an empty skip set: "git hides none of
    these" and "git would not answer" are different facts, and a walk that returned the unfiltered
    set on the second would let a step write `engines.node` into a vendored dependency and then
    record an `applied` line claiming the convention was decided here.

    **It propagates out of `manifests` and `read_all`, and every importing step must catch it at
    its own command boundary** — deliberately not folded into `Manifest.error`, which means "this
    file could not be read" and answers 3 everywhere. The codes differ by command: `verify` owes
    2, the shape having gone unobserved rather than observed and found wrong; `probe` owes 2 as
    well, printing the question, because a probe exiting 3 ends the whole `/adopt` walk and leaves
    the repo no route to `n/a` at all; `apply` owes 3. A step that omits the catch gets
    `_dispatch`'s traceback and exit 3, which `audit` records as FAILED against a shape nobody
    looked at.
    """


def manifests(root: str) -> list[str]:
    """Every package.json in `root` that a person maintains, repo-relative and sorted.

    Raises `GitRefused` when the second filter could not be applied — see that exception.
    """
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        kept = sorted(name for name in dirs if name not in GENERATED)
        dirs[:] = _own_fixtures.prune(base, kept)
        if "package.json" in files:
            found.append(os.path.relpath(os.path.join(base, "package.json"), root).replace(os.sep, "/"))
    hidden, refusal = _gitignore.ignored_untracked(root, found)
    if refusal:
        raise GitRefused(f"{refusal}, so which of the {len(found)} package.json file(s) here are a project's "
                         f"could not be established")
    return sorted(rel for rel in found if rel not in hidden)


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
    """Every project manifest, read. A caller checks `error` before trusting `data`.

    A `GitRefused` from the walk propagates rather than arriving as a `Manifest.error`, and that
    is deliberate: `error` means "this file could not be read", which a step answers with exit 3
    in every command, while "git would not say which files are a project's" is a different fact
    and `verify` owes it exit 2 — the shape was never observed, not observed and found wrong.
    Collapsing the two would have `verify` assert a repo is out of shape on no evidence. Each step
    catches it at its own command boundary, where which command is running is known.
    """
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
