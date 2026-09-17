"""A docs site's just-the-docs remote_theme carries a ref, and the halves around it hold.

A `remote_theme` with no `@<ref>` resolves to the theme repository's default branch on every
rebuild, so the version serving the site is not knowable from the repo and moves under it with
nothing committed here — a layout the pages depend on can change, and so can whether an override
under `_includes/` or `_sass/` still reaches the theme file it shadows.

The tag itself is a constant in the prose of the version that introduced this rule, which is where
the migration reads it from and the one place it lives. So what is asserted here is that a ref is
there, never which one: a rule keyed on today's tag would fail every conforming repo the morning
the theme is bumped, and the bump is a deliberate edit to one line of one file.

The config is read as lines rather than parsed as YAML: PyYAML is not in the interpreter every
machine runs this with, and the line numbers are what make a finding point somewhere. What makes a
line scan safe is that it refuses — a duplicate `remote_theme`, one nested under another key, a
`theme:` beside the remote one, or a value that is not `owner/name` are each reported with their
line, because which value Jekyll ends up serving is not a guess this rule gets to make.

The plugins list and the page tree belong to the github-pages skill and are asserted here, never
written. Naming them is what stops a clean run claiming the whole convention was checked when only
the pin was.
"""

from __future__ import annotations

import os
import re
from typing import NamedTuple

CONFIG = "docs/_config.yml"
INDEX = "docs/index.md"
PAGES = "docs/pages"
THEME = "just-the-docs/just-the-docs"
PLUGIN = "jekyll-remote-theme"

# A key at the top level of the config — the only level Jekyll reads these from — and the same
# shape at an indent, which is a sub-key of something else and not the site's theme.
KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*):(.*)$")
NESTED_RE = re.compile(r"^[ \t]+([A-Za-z_][\w.-]*):")
# A `#` opens a YAML comment only at the start of a token, so `a#b` is a value and `a #b` is not.
COMMENT_RE = re.compile(r"(?:^|(?<=\s))#.*$")
VALUE_RE = re.compile(r"^([\w.-]+/[\w.-]+)(?:@(\S+))?$")


class Line(NamedTuple):
    no: int
    text: str


class Config(NamedTuple):
    remote: list[Line]          # remote_theme: at the top level, in file order
    nested: list[Line]          # remote_theme: at an indent — a sub-key of something, not the theme
    themes: list[Line]          # theme: at the top level, the gem-based sibling of remote_theme
    plugins: list[str]          # the plugin names listed
    plugin_problems: list[str]  # lines inside the plugins block the reader could not classify


class Pin(NamedTuple):
    kind: str   # "pinned" · "unpinned" · "other" — a theme repository that is not just-the-docs
    owner: str
    ref: str    # the tag, "" unless pinned


def read_lines(path: str) -> list[Line]:
    """Every line with its number. Raises when the file is there and will not open.

    A config on disk that cannot be read leaves the theme unobserved rather than observed and found
    wrong, so this refuses and the runner reports the rule unmeasured.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise OSError(f"{CONFIG} is on disk and would not open ({exc}), so the theme it sets was never read") from exc
    return [Line(number, text) for number, text in enumerate(raw.splitlines(), 1)]


def clean(value: str) -> str:
    """A scalar with its trailing comment and surrounding quotes removed."""
    text = COMMENT_RE.sub("", value).strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def flow_items(value: str) -> list[str]:
    """The entries of an inline `[a, b]` list, or the single scalar a key was given."""
    if value.startswith("[") and value.endswith("]"):
        return [clean(part) for part in value[1:-1].split(",") if part.strip()]
    return [value] if value else []


def parse(lines: list[Line]) -> Config:
    """Classify the config far enough to answer what theme it sets and what plugins it loads.

    A block sequence written at the key's own indent is valid YAML and occurs in the fleet, so the
    plugins reader accepts it; anything inside that block it cannot read as an item is reported
    rather than skipped.
    """
    remote: list[Line] = []
    nested: list[Line] = []
    themes: list[Line] = []
    plugins: list[str] = []
    problems: list[str] = []
    in_plugins = False
    for line in lines:
        bare = line.text.strip()
        if not bare or bare.startswith("#"):
            continue
        key_match = KEY_RE.match(line.text)
        if key_match:
            key, value = key_match.group(1), clean(key_match.group(2))
            in_plugins = key == "plugins"
            if in_plugins:
                plugins.extend(flow_items(value))
            elif key == "remote_theme":
                remote.append(line)
            elif key == "theme":
                themes.append(line)
            continue
        if in_plugins:
            if bare.startswith("- "):
                plugins.append(clean(bare[2:]))
            else:
                problems.append(f"line {line.no}: {line.text}")
            continue
        nested_match = NESTED_RE.match(line.text)
        if nested_match and nested_match.group(1) == "remote_theme":
            nested.append(line)
    return Config(remote, nested, themes, plugins, problems)


def classify(line: Line) -> Pin | None:
    """What one remote_theme line names, or None when its value is not `owner/name`."""
    match = VALUE_RE.match(clean(line.text.partition(":")[2]))
    if match is None:
        return None
    owner, ref = match.group(1), match.group(2) or ""
    if owner != THEME:
        return Pin("other", owner, ref)
    return Pin("pinned" if ref else "unpinned", owner, ref)


def read_pin(cfg: Config) -> tuple[Pin | None, list[str]]:
    """The one remote_theme line this rule reads, or the sentences saying why there is none."""
    problems: list[str] = []
    if len(cfg.remote) > 1:
        problems.append(f"{CONFIG} sets remote_theme more than once, and a duplicate key resolves to the "
                        f"last one — a ref on the first would leave the site unpinned while the file says "
                        f"otherwise:")
        problems.extend(f"  line {line.no}: {line.text}" for line in cfg.remote)
        return None, problems
    if cfg.remote and cfg.themes:
        problems.append(f"{CONFIG} sets both remote_theme and theme, and which one serves the site is not "
                        f"readable from the file:")
        problems.extend(f"  line {line.no}: {line.text}" for line in cfg.remote + cfg.themes)
        return None, problems
    if not cfg.remote:
        if cfg.nested:
            problems.append(f"{CONFIG} holds a remote_theme key at an indent, which makes it a sub-key of "
                            f"something rather than the site's own theme:")
            problems.extend(f"  line {line.no}: {line.text}" for line in cfg.nested)
        elif cfg.themes:
            names = ", ".join(clean(line.text.partition(":")[2]) for line in cfg.themes)
            problems.append(f"{CONFIG} sets theme: {names} rather than a remote_theme, so the site is served "
                            f"by a gem-based theme and the shape this rule asserts is {THEME} carrying a ref")
        else:
            problems.append(f"{CONFIG} names no theme at all, neither remote_theme nor theme, so the site "
                            f"is served by whatever Jekyll defaults to and there is no ref here to read.")
        return None, problems
    pin = classify(cfg.remote[0])
    if pin is None:
        problems.append(f"{CONFIG} sets a remote_theme this rule cannot read as `owner/name` or "
                        f"`owner/name@ref`:")
        problems.append(f"  line {cfg.remote[0].no}: {cfg.remote[0].text}")
        return None, problems
    return pin, problems


def other_halves(root: str, cfg: Config) -> list[str]:
    """The parts of the target shape this rule asserts and never writes."""
    out: list[str] = []
    if PLUGIN not in cfg.plugins:
        out.append(f"{CONFIG} does not list {PLUGIN} under plugins, so Jekyll never loads the plugin that "
                   f"reads remote_theme at all")
    out.extend(f"the plugins block holds a line this rule cannot read as a list item — {problem}"
               for problem in cfg.plugin_problems)
    if not os.path.isfile(os.path.join(root, *INDEX.split("/"))):
        out.append(f"there is no {INDEX}, so the pin would be asserted about a site with no home page")
    if not os.path.isdir(os.path.join(root, *PAGES.split("/"))):
        out.append(f"there is no {PAGES}/, so the pin would be asserted about a site with no pages")
    return out


def check(root: str) -> list[str]:
    """One line per part of the docs shape that does not hold, empty when the site is pinned."""
    path = os.path.join(root, *CONFIG.split("/"))
    if not os.path.isfile(path):
        # A repo publishing no Jekyll site has no remote_theme to be pinned or unpinned, so the rule
        # holds with nothing to say. Positive evidence rather than a silence: the one file Jekyll
        # reads a theme from was looked for and is not there, and nothing here ever creates one.
        return []
    cfg = parse(read_lines(path))
    pin, problems = read_pin(cfg)
    violations = list(problems)
    if pin is not None and pin.kind != "pinned":
        violations.append(f"{CONFIG} sets remote_theme to {pin.owner}"
                          f"{'' if pin.kind == 'other' else ' with no @<ref> after it'}, and the shape this "
                          f"rule asserts is {THEME} carrying a ref")
    violations.extend(other_halves(root, cfg))
    return violations
