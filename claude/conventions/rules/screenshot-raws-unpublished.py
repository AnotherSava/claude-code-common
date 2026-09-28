"""A repo committing raw screenshot captures keeps them out of its published docs site.

The docs-relevance skill commits each frame's untouched capture beside it, at
`docs/screenshots/raw/<name>`, so a frame can be re-framed on either machine without a re-shoot.
Jekyll publishes every file under `docs/` it is not told to leave out, so without an `exclude:`
entry each raw goes live next to the frame made from it: a second copy of every screenshot, with no
page linking it and nothing reporting that it is there.

The config is read as lines rather than parsed as YAML, for the reason `docs-theme-pinned` gives:
PyYAML is not in every interpreter this runs under, and the line numbers are what make a finding
point somewhere. A line inside the `exclude:` block that does not read as a list item is reported
rather than skipped, since a skipped line could be the entry this rule is looking for.
"""

from __future__ import annotations

import os
import re

import _git

CONFIG = "docs/_config.yml"
RAW = "docs/screenshots/raw"
# The entry, as Jekyll resolves it: relative to `docs/`, the source directory. Jekyll 3.10, which
# GitHub Pages runs, joins each entry onto the source with File.join and matches a path that starts
# with the result or that File.fnmatch? matches as a glob, so a leading `/` collapses harmlessly,
# the `/*` and `/**` forms work through the glob, `./` normalises nothing and matches nothing, and
# the bare `screenshots/raw` also drops every published frame whose name begins `raw`.
ENTRY = "screenshots/raw"
ACCEPTED = {f"{ENTRY}/", f"{ENTRY}/*", f"{ENTRY}/**"}

KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*):(.*)$")
COMMENT_RE = re.compile(r"(?:^|(?<=\s))#.*$")


def clean(value: str) -> str:
    """A scalar with its trailing comment and surrounding quotes removed."""
    text = COMMENT_RE.sub("", value).strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def normalise(entry: str) -> str:
    """An exclude entry as Jekyll matches it: one leading `/` dropped, since File.join collapses it."""
    return entry[1:] if entry.startswith("/") else entry


def raw_files(root: str) -> list[str]:
    """Every file under the raw directory that git does not hide, repo-relative."""
    base = os.path.join(root, *RAW.split("/"))
    found = []
    for folder, _, names in os.walk(base):
        for name in names:
            found.append(os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/"))
    hidden = _git.ignored_untracked(root, found)
    return [path for path in found if path not in hidden]


def read_excludes(path: str) -> tuple[list[str], list[str]]:
    """The exclude entries the config lists, and the lines about it this reader could not settle.

    Raises when the file is on disk and will not open: an unread config is not one found wanting.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise OSError(f"{CONFIG} is on disk and would not open ({exc}), so what it excludes was never read") from exc
    entries: list[str] = []
    problems: list[str] = []
    keys = 0
    inside = False
    for number, text in enumerate(lines, 1):
        bare = text.strip()
        if not bare or bare.startswith("#"):
            continue
        key = KEY_RE.match(text)
        if key:
            inside = key.group(1) == "exclude"
            if inside:
                keys += 1
                value = clean(key.group(2))
                if value.startswith("[") and value.endswith("]"):
                    entries.extend(clean(part) for part in value[1:-1].split(",") if part.strip())
                elif value:
                    problems.append(f"line {number}: {text}")
            continue
        if inside:
            if bare.startswith("- "):
                entries.append(clean(bare[2:]))
            elif text[:1] in " \t":
                problems.append(f"line {number}: {text}")
            else:
                inside = False
    if keys > 1:
        problems.insert(0, f"{CONFIG} sets exclude more than once, and a duplicate key resolves to the last one")
    return entries, problems


def check(root: str) -> list[str]:
    """One line per reason the raws would be published, empty when they are kept out or there are none."""
    if not os.path.isdir(os.path.join(root, *RAW.split("/"))):
        return []
    raws = raw_files(root)
    config = os.path.join(root, *CONFIG.split("/"))
    if not raws or not os.path.isfile(config):
        # No raw git keeps, or no Jekyll site to publish one: both are looked for and absent, and
        # nothing here creates either.
        return []
    entries, problems = read_excludes(config)
    if problems:
        return [f"{CONFIG}'s exclude list holds lines this rule cannot read as list items, so whether "
                f"{ENTRY}/ is among them is not known:"] + [f"  {problem}" for problem in problems]
    listed = {normalise(entry) for entry in entries}
    if listed & ACCEPTED:
        return []
    if ENTRY in listed:
        return [f"{CONFIG} excludes the bare `{ENTRY}`, which keeps the raws off the site but, matched by "
                f"prefix, also drops every published file whose path begins `{ENTRY}` — replace it with "
                f"`{ENTRY}/`"]
    return [f"{RAW}/ holds {len(raws)} raw capture(s) and {CONFIG} does not exclude {ENTRY}/, so the "
            f"site publishes every one of them beside the frame made from it — add `- {ENTRY}/` to its "
            f"exclude: list"]
