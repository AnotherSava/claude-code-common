"""Which package.json files in a repo a person maintains, and how to read one.

The Node rules — the engines range, the engine-strict enforcement, the package-manager pin — all
answer the same question before they look at anything, and they have to answer it identically. A
repo whose app lives under `web/` carries `web/.next/package.json` and one package.json per
installed dependency under `web/node_modules/`; a plain walk returns all of them, and a rule that
asserted against one of those would be asserting against a tree the next build replaces. Worse,
two rules disagreeing about the set is a repo where one of them reports on manifests the other
never looked at.

So the set is derived once, here, by two filters a caller never chooses between. The walk never
descends into a directory a build tool owns, and what survives it is then narrowed to what git does
not hide — a name rule cannot see a scratch clone, and the global convention puts scratch in a
gitignored `tmp/`, so a manifest inside one is a designed and recurring condition rather than an
accident. Everything a caller gets back is repo-relative with forward slashes, so a path reads the
same on both machines.

Narrowing this set is a **detection fix**, and it reaches every repo at once by design: the repo
was mismeasured rather than changed, so there is nothing for anyone to adopt. A rule that asserts
something *stricter* than it did yesterday is the other case, and that is a new version rather than
an edit here — the two are told apart by whether a conforming repo now has work to do.

Nothing in here reports a file it could not read as a file it read. A manifest that will not parse
raises, so the runner records the rule as unmeasured instead of letting a rule count it as one more
manifest with nothing wrong.
"""

import json
import os
from typing import NamedTuple

import _git

# Directories a build tool, a package manager or a language toolchain owns. A package.json below
# one of these is generated output, a vendored copy, or an installed dependency — never a manifest
# anybody edits. The first four are the set the fleet survey measured
# (`web/.next/standalone/package.json` is the case that named this list); the rest are the same
# shape from the other toolchains these repos use, listed so a repo that gains one later does not
# quietly start reporting a build artefact as a project.
#
# Both `.venv` and `venv` are here because both are ordinary spellings and only the first was listed
# at first: two Python repos in the fleet were measured reading
# `venv/Lib/site-packages/playwright/driver/package/package.json` as a project of theirs, which
# declares `engines.node`, and an approved walk would have written an `.npmrc` inside a virtualenv
# the next rebuild deletes.
GENERATED = (".angular", ".cache", ".git", ".next", ".nuxt", ".output", ".parcel-cache",
             ".pnpm-store", ".svelte-kit", ".turbo", ".venv", ".vercel", ".yarn", "bower_components",
             "build", "coverage", "dist", "node_modules", "out", "storybook-static", "target", "vendor",
             "venv")


class Unreadable(Exception):
    """A file that is there and would not read, so what it declares was never established.

    Distinct from absence, which is an answer: a manifest with no `.nvmrc` beside it tells a rule
    something, while a manifest that is not valid JSON tells it nothing at all. Raised rather than
    returned for the same reason `_git.GitRefused` is — a rule holding a reason string can drop it,
    and a dropped reason becomes a pass.
    """


class Manifest(NamedTuple):
    rel: str    # repo-relative, forward slashes
    data: dict  # the parsed object


def manifests(root: str) -> list[str]:
    """Every package.json in `root` that a person maintains, repo-relative and sorted."""
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in GENERATED)
        if "package.json" in files:
            found.append(os.path.relpath(os.path.join(base, "package.json"), root).replace(os.sep, "/"))
    try:
        hidden = _git.ignored_untracked(root, found)
    except _git.GitRefused as exc:
        raise _git.GitRefused(f"{exc}, so which of the {len(found)} package.json file(s) here are a "
                              f"project's could not be established") from exc
    return sorted(rel for rel in found if rel not in hidden)


def read(root: str, rel: str) -> Manifest:
    """One manifest, parsed. Raises when it cannot be read as a JSON object."""
    path = os.path.join(root, *rel.split("/"))
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{rel} could not be read ({exc})") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise Unreadable(f"{rel} is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise Unreadable(f"{rel} does not hold a JSON object at its top level")
    return Manifest(rel, data)


def read_all(root: str) -> list[Manifest]:
    """Every project manifest, read."""
    return [read(root, rel) for rel in manifests(root)]


def sibling(rel: str, name: str) -> str:
    """The repo-relative path of `name` beside a manifest — its `.nvmrc`, its `.npmrc`.

    Beside, and never above: npm resolves the project config from the directory holding
    package.json, so an `.npmrc` at a repo root is not read at all when npm runs in `web/`.
    """
    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    return f"{parent}/{name}" if parent else name


def read_text(root: str, rel: str) -> str | None:
    """A sibling file's text, or None when there is no such file.

    Absence is the answer a rule acts on — no `.nvmrc` beside a manifest means the Node version this
    project targets is written nowhere in the repo, which is a finding. A file that exists and will
    not read is the other case entirely, and it raises: reporting "no `.npmrc` here" for an `.npmrc`
    sitting right there is a wrong answer rather than a missing one.
    """
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as handle:
            return handle.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{rel} is there and could not be read ({exc})") from exc
