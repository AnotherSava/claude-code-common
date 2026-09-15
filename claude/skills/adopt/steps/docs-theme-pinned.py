#!/usr/bin/env python3
"""v11 — pin a docs site's just-the-docs remote_theme to a tag.

A `remote_theme` with no `@<ref>` resolves to the theme repository's default branch on
every rebuild, so the version serving the site is not knowable from the repo and moves
under it with nothing committed here — a layout the pages depend on can change, and so
can whether an override under `_includes/` or `_sass/` still reaches the theme file it
shadows. Appending a tag is the whole change.

Three rules shape everything below.

**The tag is read out of this step's own prose, never from the network.** A step never
resolves a value over the wire (contract rule 4), and one it cannot resolve it must not
guess. Keeping the constant in `docs-theme-pinned.md` puts it in the file the user reads
while walking the step, so a bump is one prose edit with nothing to keep in sync.

**One line changes, and the run proves it.** The rewrite is planned as an explicit list of
lines, written to a sibling temp file, asserted against that plan, and only then moved
over the original — so the file on disk is never the half-written one. Afterwards every
line is read back and compared against the plan, pairwise on text: a line that came out
different is named verbatim rather than counted.

**A file the parser cannot read stops the step.** Two `remote_theme` keys, one nested
under another key, a value that is not `owner/name`, or a `theme:` key beside the remote
one: each is printed with its line number and nothing is written. Which value Jekyll ends
up serving is not a guess this step gets to make.

    docs-theme-pinned.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    docs-theme-pinned.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, file intact
    docs-theme-pinned.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the evidence behind
it. The note is one line and carries no tab, because it becomes a field in a TSV record.
"""

import os
import re
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert
# is what lets the authoring gate import this module directly as well.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

CONFIG = "docs/_config.yml"
INDEX = "docs/index.md"
PAGES = "docs/pages"
THEME = "just-the-docs/just-the-docs"
PLUGIN = "jekyll-remote-theme"

# The prose is the one place the tag lives. Reached from this file's own directory rather than
# from the cwd, because /adopt runs a step against a repo that is not this one.
PROSE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "docs-theme-pinned.md")
PIN_RE = re.compile(rf"^remote_theme:[ \t]*{re.escape(THEME)}@(\S+)[ \t]*$", re.M)

# A key at the top level of the config — the only level Jekyll reads these from — and the same
# shape at an indent, which is a sub-key of something else and not the site's theme.
KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*):(.*)$")
NESTED_RE = re.compile(r"^[ \t]+([A-Za-z_][\w.-]*):")
# A `#` opens a YAML comment only at the start of a token, so `a#b` is a value and `a #b` is not.
COMMENT_RE = re.compile(r"(?:^|(?<=\s))#.*$")
VALUE_RE = re.compile(r"^([\w.-]+/[\w.-]+)(?:@(\S+))?$")

# Inserted above the line this step rewrites, so the next reader of the file knows what the
# missing ref did without going and finding this step.
NOTE = (
    "# Pinned. Without a ref, jekyll-remote-theme rebuilds from the theme's default branch on every",
    "# build, so a layout these pages depend on can change with nothing committed in this repo. It",
    "# also decides whether an override under _includes/ or _sass/ still reaches the theme file it",
    "# shadows. Bump it deliberately, like any other dependency.",
)

# Print file content back verbatim whatever the console codepage is. A description holding an
# em-dash through Windows' cp1252 default raises rather than prints, which would turn a healthy
# run into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class Line(NamedTuple):
    no: int
    text: str  # without its terminator
    end: str   # the terminator exactly as it was on disk, "" on a last line carrying none


class Config(NamedTuple):
    lines: list[Line]
    remote: list[Line]        # remote_theme: at the top level, in file order
    nested: list[Line]        # remote_theme: at an indent — a sub-key of something, not the theme
    themes: list[Line]        # theme: at the top level, the gem-based sibling of remote_theme
    plugins: list[str]        # the plugin names listed
    plugin_problems: list[str]  # lines inside the plugins block the parser could not classify


class Pin(NamedTuple):
    kind: str   # "pinned" · "unpinned" · "other" — a theme repository that is not just-the-docs
    owner: str
    ref: str    # the tag, "" unless pinned


class Plan(NamedTuple):
    lines: list[Line]   # the exact file to write
    kept: list[str]     # the text of every line that came from the original, in order
    inserted: int       # note lines added above the rewritten one


def read_lines(path: str) -> list[Line] | None:
    """Every line with its own terminator preserved, or None when the file will not open.

    Terminators are kept per line rather than normalised so that rewriting one line of a
    CRLF checkout does not rewrite all of them. Joining text and end back together
    reproduces the file byte for byte, which is what makes "nothing else changed" an
    assertion rather than a hope.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError):
        return None
    parts = raw.split("\n")
    out: list[Line] = []
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if last and not part:
            break
        carriage = part.endswith("\r")
        out.append(Line(index + 1, part[:-1] if carriage else part, "" if last else ("\r\n" if carriage else "\n")))
    return out


def render(lines: list[Line]) -> str:
    return "".join(f"{line.text}{line.end}" for line in lines)


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

    Deliberately not a YAML parse: PyYAML is not in the interpreter every machine runs this
    with, and a full parse loses the line numbers and the surrounding text that a one-line
    surgical rewrite needs. A block sequence written at the key's own indent is valid YAML
    and occurs in the fleet, so the plugins reader accepts it; anything inside that block it
    cannot read as an item is reported rather than skipped.
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
    return Config(lines, remote, nested, themes, plugins, problems)


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
    """The one remote_theme line this step may touch, or the sentences saying why there is none.

    Both probe and apply read the file through here, so the question one asks and the refusal
    the other prints can never describe different files.
    """
    problems: list[str] = []
    if len(cfg.remote) > 1:
        problems.append(f"{CONFIG} sets remote_theme more than once, and a duplicate key resolves to the "
                        f"last one — pinning the first would leave the site unpinned while the file says "
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
            problems.append(f"{CONFIG} sets theme: {names} rather than a remote_theme. A gem-based theme "
                            f"chosen on purpose and a site nobody has migrated read identically from the "
                            f"file, so this step will not change it.")
        else:
            problems.append(f"{CONFIG} names no theme at all, neither remote_theme nor theme, so the site "
                            f"is served by whatever Jekyll defaults to and there is no line here to pin.")
        return None, problems
    pin = classify(cfg.remote[0])
    if pin is None:
        problems.append(f"{CONFIG} sets a remote_theme this step cannot read as `owner/name` or "
                        f"`owner/name@ref`:")
        problems.append(f"  line {cfg.remote[0].no}: {cfg.remote[0].text}")
        return None, problems
    return pin, problems


def other_halves(root: str, cfg: Config) -> list[str]:
    """The parts of the target shape this step asserts and never writes.

    A plugins list and a page tree belong to the github-pages skill. Naming them here is what
    stops the recorded note claiming the whole convention was checked when only the pin was.
    """
    out: list[str] = []
    if PLUGIN not in cfg.plugins:
        out.append(f"{CONFIG} does not list {PLUGIN} under plugins, so Jekyll never loads the plugin that "
                   f"reads remote_theme at all")
    out.extend(f"the plugins block holds a line this step cannot read as a list item — {problem}"
               for problem in cfg.plugin_problems)
    if not os.path.isfile(os.path.join(root, *INDEX.split("/"))):
        out.append(f"there is no {INDEX}, so the pin would be asserted about a site with no home page")
    if not os.path.isdir(os.path.join(root, *PAGES.split("/"))):
        out.append(f"there is no {PAGES}/, so the pin would be asserted about a site with no pages")
    return out


def tag_from_prose() -> tuple[str, str]:
    """(tag, problem) — the pin named in this step's prose, the only place that value lives."""
    name = os.path.basename(PROSE)
    try:
        with open(PROSE, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        return "", (f"{name} could not be read ({exc}), and the tag to pin to is written there rather than "
                    f"in this script or looked up over the network")
    found = PIN_RE.findall(text)
    if len(found) != 1:
        return "", (f"{name} holds {len(found)} line(s) reading `remote_theme: {THEME}@<tag>`, and exactly "
                    f"one of them is the tag this step pins to")
    return found[0], ""


def pinned_text(target: Line, tag: str) -> str:
    """The rewritten line, keeping its own quoting, spacing and trailing comment.

    Built by splitting at the first colon and inserting into the value, so a trailing comment
    that happens to repeat the theme's name is never the thing that gets the tag.
    """
    key, colon, value = target.text.partition(":")
    head, _, tail = value.partition(THEME)
    return f"{key}{colon}{head}{THEME}@{tag}{tail}"


def plan_rewrite(lines: list[Line], target: Line, tag: str) -> Plan:
    """The exact file to write: one line rewritten, the note above it unless one is already there.

    Skipping the note when the line above is already a comment leaves an author's own
    explanation alone rather than wedging this one between it and the line it explains.
    """
    above = next((line for line in reversed(lines[:target.no - 1]) if line.text.strip()), None)
    commented = above is not None and above.text.strip().startswith("#")
    end = target.end or "\n"
    out: list[Line] = []
    kept: list[str] = []
    inserted = 0
    for line in lines:
        if line.no == target.no:
            if not commented:
                for note in NOTE:
                    out.append(Line(len(out) + 1, note, end))
                    inserted += 1
            text = pinned_text(target, tag)
            out.append(Line(len(out) + 1, text, line.end))
            kept.append(text)
            continue
        out.append(Line(len(out) + 1, line.text, line.end))
        kept.append(line.text)
    return Plan(out, kept, inserted)


def compare(expected: list[Line], actual: list[Line]) -> list[str]:
    """One sentence per line that came out different — named verbatim, never tallied."""
    out: list[str] = []
    for index in range(max(len(expected), len(actual))):
        want = expected[index].text if index < len(expected) else None
        got = actual[index].text if index < len(actual) else None
        if want != got:
            out.append(f"line {index + 1}: wrote {want!r}, read back {got!r}")
    return out


def write_config(path: str, text: str) -> str:
    """Write beside the file, assert, then move over it — so the original survives every failure.

    newline="\\n" so the two machines sharing these repos never see a whole-file line-ending
    diff; each line already carries the terminator it had on disk, so an existing CRLF file
    stays CRLF and only the rewritten line differs.
    """
    tmp = f"{path}.adopt-tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written = read_lines(tmp)
        if written is None or render(written) != text:
            os.remove(tmp)
            return f"{os.path.basename(tmp)} did not read back as it was written"
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return str(exc)
    return ""


def cmd_probe(root: str) -> int:
    path = os.path.join(root, *CONFIG.split("/"))
    if not os.path.isfile(path):
        # Positive evidence about the convention's own precondition: no Jekyll site is published
        # from this repo, and this step never creates one. Unlike a missing backlog, an absent
        # docs site is not something the conventions require anyone to have.
        print(f"no {CONFIG} in this repo, so it publishes no Jekyll site and there is no theme line to "
              f"pin; this step never creates one")
        return 1
    lines = read_lines(path)
    if lines is None:
        print(f"{CONFIG} is on disk and would not open, so nothing about the site was observed")
        return 3
    cfg = parse(lines)
    pin, problems = read_pin(cfg)
    if pin is None:
        for text in problems:
            print(text)
        print("Resolve that by hand and re-run this step, or record n/a if the divergence is deliberate.")
        return 2
    if pin.kind == "other":
        print(f"{CONFIG} pins remote_theme to {pin.owner}, which is not {THEME}. A theme chosen on purpose "
              f"and a site nobody has migrated read identically from the file, so moving it is a rewrite of "
              f"the site's styling and a human's call. Record n/a if the divergence is deliberate.")
        return 2
    if pin.kind == "unpinned":
        print(f"{CONFIG} sets remote_theme to {THEME} with no @<ref>, so the site rebuilds from the theme's "
              f"default branch and the version serving it is not knowable from this repo")
        return 0
    rest = other_halves(root, cfg)
    if rest:
        print(f"{CONFIG} already pins remote_theme to {THEME}@{pin.ref}, but the rest of the shape does not "
              f"hold and this step writes none of it:")
        for text in rest:
            print(f"  {text}")
        print("Fix that by hand — the github-pages skill owns the plugins list and the page tree — then "
              "re-run this step, or record declined.")
        return 2
    # Positive evidence read off the file: the pin is there and the halves around it hold, which is
    # what a site pinned before this step existed looks like.
    print(f"already pinned: {CONFIG} sets remote_theme to {THEME}@{pin.ref}, lists {PLUGIN} under plugins, "
          f"and both {INDEX} and {PAGES}/ are present")
    return 1


def cmd_apply(root: str, dry_run: bool) -> int:
    path = os.path.join(root, *CONFIG.split("/"))
    if not os.path.isfile(path):
        print(f"there is no {CONFIG} here to pin, which is a question about whether this repo publishes a "
              f"site at all rather than an apply — nothing was written")
        return 3
    lines = read_lines(path)
    if lines is None:
        print(f"{CONFIG} is on disk and would not open — nothing was written")
        return 3
    cfg = parse(lines)
    pin, problems = read_pin(cfg)
    if pin is None:
        for text in problems:
            print(text)
        print(f"{CONFIG} is untouched — which value the site ends up serving is not this step's guess.")
        return 3
    if pin.kind == "other":
        print(f"{CONFIG} pins remote_theme to {pin.owner} rather than {THEME}, and changing which theme a "
              f"site uses is a rewrite of its styling — {CONFIG} is untouched")
        return 3
    if pin.kind == "pinned":
        # A second apply, where the first already wrote the tag. Exits 0 rather than raising: the
        # code an uncaught exception leaves behind is 1, which means "does not apply" everywhere
        # else in this system and would record the repo as never needing the step.
        print(f"already pinned: {CONFIG} sets remote_theme to {THEME}@{pin.ref}, so there is nothing to "
              f"append and the file is untouched")
        return 0
    tag, problem = tag_from_prose()
    if problem:
        print(f"{problem} — {CONFIG} is untouched")
        return 3
    target = cfg.remote[0]
    plan = plan_rewrite(lines, target, tag)
    survivors = [line.text if line.no != target.no else pinned_text(target, tag) for line in lines]
    if plan.kept != survivors:
        print(f"the planned rewrite does not carry every line of {CONFIG} through unchanged, so nothing "
              f"was written:")
        for text in compare([Line(0, t, "") for t in survivors], [Line(0, t, "") for t in plan.kept]):
            print(f"  {text}")
        return 3
    if dry_run:
        print(f"line {target.no}  {target.text}")
        print(f"       ->  {pinned_text(target, tag)}")
        for note in NOTE[:plan.inserted]:
            print(f"insert    {note}")
        print(f"{CONFIG} would gain the @{tag} pin on its remote_theme line and {plan.inserted} note "
              f"line(s) above it; {len(lines)} existing line(s) unchanged")
        return 0
    failure = write_config(path, render(plan.lines))
    if failure:
        print(f"could not write {CONFIG} ({failure}) — the file is untouched and a re-run picks up where "
              f"this stopped")
        return 3
    actual = read_lines(path)
    if actual is None:
        print(f"{CONFIG} was written and will not read back, so what is on disk could not be asserted")
        return 3
    differences = compare(plan.lines, actual)
    for text in differences:
        print(f"CHANGED     {text}")
    if differences:
        print(f"{CONFIG} on disk does not match what this step planned to write — read the lines above "
              f"before committing anything")
        return 3
    print(f"ok          line {target.no} -> {pinned_text(target, tag)}")
    if plan.inserted:
        print(f"ok          {plan.inserted} note line(s) inserted above it")
    print(f"ok          {len(lines) - 1} other line(s) read back from disk and compared one by one, "
          f"each unchanged")
    print(f"{CONFIG} remote_theme pinned to {THEME}@{tag}; every other line re-read from disk and "
          f"asserted unchanged")
    return 0


def cmd_verify(root: str) -> int:
    """Is this repo in the shape the convention requires — never, was a pin written here.

    A pin is a one-line edit that leaves no trace of having been made, so a check keyed on
    history would report NOT COVERED for the repo that pinned its theme before this step
    existed, and /adopt would fall through to probe and file it as never needing the step.
    """
    path = os.path.join(root, *CONFIG.split("/"))
    if not os.path.isfile(path):
        # Exit 2 rather than 3, per CD1: a repo publishing no Jekyll site has no remote_theme to be
        # pinned or unpinned, so the shape is unobservable rather than violated. Both codes send
        # /adopt on to probe, which is what turns this into `n/a` with positive evidence — the
        # danger a verify has to avoid here is exit 0, and neither of these is that. Exit 2 is also
        # what every sibling step returns for "this repo holds no subject to assert about".
        print(f"there is no {CONFIG} here, so this repo publishes no Jekyll site and has no "
              f"remote_theme whose pinning could be asserted either way")
        return 2
    lines = read_lines(path)
    if lines is None:
        print(f"{CONFIG} is on disk and would not open, so the theme it sets cannot be observed")
        return 2
    cfg = parse(lines)
    pin, problems = read_pin(cfg)
    failures = list(problems)
    if pin is not None and pin.kind != "pinned":
        failures.append(f"{CONFIG} sets remote_theme to {pin.owner}"
                        f"{'' if pin.kind == 'other' else ' with no @<ref> after it'}, and the shape this "
                        f"step asserts is {THEME} carrying a ref")
    failures.extend(other_halves(root, cfg))
    for text in failures:
        print(text)
    if failures:
        return 3
    print(f"{CONFIG} pins remote_theme to {THEME}@{pin.ref}, lists {PLUGIN} under plugins, and both "
          f"{INDEX} and {PAGES}/ are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
