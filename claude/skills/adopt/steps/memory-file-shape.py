#!/usr/bin/env python3
"""v5 — every memory file opens with frontmatter, and every index entry names a bare filename.

Project memory is a directory of markdown files plus a `MEMORY.md` index beside them.
Two things make it readable by anything other than the person who wrote it: each file
opens with a `---` block saying what the memory is, and each index entry links to a
sibling by bare filename. The global index in `CLAUDE.md` describes the same files from
a different directory and so uses `~/.claude/memory/<file>.md`; markdown never expands
`~`, so a line copied from one index into the other is a link that resolves to nothing.

Nothing in the fleet needed work when this step was written — every repo holding a
memory directory was already in this shape. What the step buys is that "current" stops
meaning "nobody looked", and that `audit` re-runs `verify`, so the first repo to drift
is a finding rather than a silence.

Only the index is rewritable. A file with no frontmatter needs a human to say what the
memory is and when it was saved, and neither is recoverable from the text, so that is a
probe refusal rather than something `apply` invents (CD4 — `apply` may never guess).

    memory-file-shape.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    memory-file-shape.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, index intact
    memory-file-shape.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the per-item
evidence behind it. The note is one line and carries no tab, because it becomes a field
in a tab-separated record file.
"""

import os
import re
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert
# is what lets the authoring gate import this module directly as well.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

# Print an index line back verbatim whatever the console codepage is. These blurbs are full of
# em-dashes, and one through Windows' cp1252 default raises rather than prints — which would turn
# a step that had classified every line into an exit 3 nobody could read.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REL = ".claude/memory"
INDEX = "MEMORY.md"
# The temp file `apply` writes before replacing the index. Deliberately not ending in `.md`: one
# left behind by a killed run must never be read back as a memory file on the next pass.
TEMP = f"{INDEX}.tmp"

# A markdown link, with the target as group 1 so its span in the file is known and only those
# bytes are ever replaced. An angle-bracketed target and a trailing "title" are both matched so
# that neither reads as a shape this parser cannot classify.
LINK_RE = re.compile(r"\[[^\]\r\n]*\]\((<[^>\r\n]*>|[^()\s]*)(?:[ \t]+\"[^\"\r\n]*\")?\)")
OPENER_RE = re.compile(r"\]\(")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


class Link(NamedTuple):
    target: str  # as written, between ( and )
    start: int   # offset of the target inside the index text, so a rewrite touches nothing else
    end: int
    line_no: int
    kind: str    # "bare" · "path" · "other" — the third names no file beside the index


class Fix(NamedTuple):
    link: Link
    name: str      # the bare filename the target becomes
    ordinal: int   # which link in the index this is, so the re-read asserts this entry and not a neighbour


class Look(NamedTuple):
    base: str
    has_dir: bool
    files: list[str]        # every memory file under the directory, index excluded
    no_frontmatter: list[str]
    unreadable: list[str]
    has_index: bool
    index_unreadable: bool
    raw: str                # the index text, "" when there is none
    links: list[Link]
    problems: list[str]     # `](` shapes the parser could not read as a link, verbatim
    names: set[str]         # the files sitting beside the index, which is what a bare link may name


def read_text(path: str) -> str | None:
    """A file's text with its line endings untranslated, or None when it cannot be read.

    `newline=""` so a CRLF index stays CRLF through a rewrite: translating it would turn a
    three-target edit into a whole-file diff between the two machines sharing these repos.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def first_line(path: str) -> str | None:
    """The file's opening line, or None when it cannot be read as text at all."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readline()
    except (OSError, UnicodeDecodeError):
        return None


def line_of(raw: str, pos: int) -> int:
    return raw.count("\n", 0, pos) + 1


def column_of(raw: str, pos: int) -> int:
    return pos - raw.rfind("\n", 0, pos)


def line_text(raw: str, pos: int) -> str:
    start = raw.rfind("\n", 0, pos) + 1
    end = raw.find("\n", pos)
    return raw[start:end if end != -1 else len(raw)].rstrip()


def classify(target: str) -> str:
    """Whether a link target names a sibling file, a path, or nothing in this directory.

    An http or mailto target is a reference to something outside the directory and is read as
    such rather than failed; a `file:` one is a machine-specific absolute path, which committed
    documentation may not carry, so it fails like any other path. A two-character scheme is a
    Windows drive letter and is a path too.
    """
    text = target.strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    text = text.split("#", 1)[0]
    scheme = SCHEME_RE.match(text)
    if scheme and len(scheme.group(0)) > 2 and not text.lower().startswith("file:"):
        return "other"
    if not text:
        return "other"
    if scheme or text.startswith("~") or "/" in text or "\\" in text or text in (".", ".."):
        return "path"
    return "bare"


def basename_of(target: str) -> str:
    """The filename a target ends in — the only part a bare link may carry."""
    text = target.strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    return re.split(r"[\\/]", text.split("#", 1)[0])[-1]


def parse_index(raw: str) -> tuple[list[Link], list[str]]:
    """Every link in the index, and every `](` the parser could not read as one.

    Abort rather than skip (idempotence rule 6): a target this reader cannot classify is
    plausibly a path-shaped one, and a step that quietly walked past it would report an index
    asserted bare while one entry never was.
    """
    links: list[Link] = []
    openers: set[int] = set()
    for match in LINK_RE.finditer(raw):
        start, end = match.span(1)
        openers.add(start - 2)
        links.append(Link(match.group(1), start, end, line_of(raw, start), classify(match.group(1))))
    # Column as well as line: two unreadable link openers on one line would otherwise print the
    # same sentence twice, and a report a reader cannot tell apart is a report they skim.
    problems = [f"line {line_of(raw, m.start())} column {column_of(raw, m.start())}: {line_text(raw, m.start())}"
                for m in OPENER_RE.finditer(raw) if m.start() not in openers]
    return links, problems


def look(root: str) -> Look:
    """Everything probe, apply and verify read, gathered once so the three cannot disagree."""
    base = os.path.join(root, *REL.split("/"))
    if not os.path.isdir(base):
        return Look(base, False, [], [], [], False, False, "", [], [], set())
    files: list[str] = []
    no_frontmatter: list[str] = []
    unreadable: list[str] = []
    for parent, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names):
            if not name.lower().endswith(".md") or name == INDEX:
                continue
            rel = os.path.relpath(os.path.join(parent, name), base).replace(os.sep, "/")
            files.append(rel)
            opening = first_line(os.path.join(parent, name))
            if opening is None:
                unreadable.append(rel)
            elif opening.lstrip("\ufeff").strip() != "---":  # a BOM is Notepad's, not a missing block
                no_frontmatter.append(rel)
    index_path = os.path.join(base, INDEX)
    has_index = os.path.isfile(index_path)
    raw = read_text(index_path) if has_index else ""
    links, problems = parse_index(raw or "")
    try:
        names = {n for n in os.listdir(base) if os.path.isfile(os.path.join(base, n))}
    except OSError:
        names = set()
    return Look(base, True, files, no_frontmatter, unreadable, has_index, has_index and raw is None,
                raw or "", links, problems, names)


def deviations(seen: Look) -> tuple[list[Fix], list[str]]:
    """The targets a rewrite can settle, and the ones only a human can.

    "Exactly one file carries that basename" is satisfied by construction: the candidates are the
    files sitting beside the index, and a directory cannot hold two entries under one name. A
    target whose basename is not among them — an entry pointing at a doc elsewhere in the repo —
    is where the rewrite would invent a link, so it stops the step instead.
    """
    fixes: list[Fix] = []
    stuck: list[str] = []
    for ordinal, link in enumerate(seen.links):
        if link.kind == "other":
            continue
        name = basename_of(link.target)
        if link.kind == "bare":
            if name not in seen.names:
                stuck.append(f"line {link.line_no}: the index names {link.target}, and no such file sits "
                             f"beside it — whether it was renamed or deleted is not this step's guess")
            continue
        if name in seen.names:
            fixes.append(Fix(link, name, ordinal))
        else:
            stuck.append(f"line {link.line_no}: {link.target} is not a bare filename, and no {name} sits "
                         f"beside the index — rewriting it would point the entry at something that is not there")
    return fixes, stuck


def skeleton(raw: str, links: list[Link]) -> str:
    """The index with every link target blanked — what a rewrite must leave byte for byte."""
    out, cursor = [], 0
    for link in links:
        out.append(raw[cursor:link.start])
        out.append("\x00")
        cursor = link.end
    out.append(raw[cursor:])
    return "".join(out)


def rewrite(raw: str, fixes: list[Fix]) -> str:
    """The index with each path-shaped target replaced by its bare filename, and nothing else."""
    out, cursor = [], 0
    for fix in sorted(fixes, key=lambda f: f.link.start):
        out.append(raw[cursor:fix.link.start])
        out.append(fix.name)
        cursor = fix.link.end
    out.append(raw[cursor:])
    return "".join(out)


def refusals(seen: Look, stuck: list[str]) -> list[str]:
    """Every reason this repo's shape cannot be settled mechanically, in reading order."""
    lines: list[str] = []
    if seen.unreadable:
        lines += [f"unreadable    {REL}/{rel}" for rel in seen.unreadable]
    if seen.index_unreadable:
        lines.append(f"unreadable    {REL}/{INDEX}")
    if seen.no_frontmatter:
        lines += [f"no --- block  {REL}/{rel}" for rel in seen.no_frontmatter]
        lines.append("A memory file's frontmatter says what the memory is and when it was saved, and "
                     "neither is recoverable from the text, so this step never writes one. Add the block "
                     "by hand — or unlock the repo, since a transcrypt-encrypted memory reads as base64 "
                     "until it is — and re-run.")
    if seen.files and not seen.has_index:
        lines.append(f"{len(seen.files)} memory file(s) under {REL}/ with no {INDEX} beside them. Writing "
                     f"the index means summarising each memory in a line, which is a human's sentence.")
    if seen.problems:
        lines.append(f"{REL}/{INDEX} holds {len(seen.problems)} line(s) this step cannot read as a link:")
        lines += [f"  {problem}" for problem in seen.problems]
    lines += stuck
    return lines


def cmd_probe(root: str) -> int:
    seen = look(root)
    if not seen.has_dir:
        # Positive evidence, read off the directory that is not there: no project memory has been
        # saved in this repo, and this step never creates any (CD4).
        print(f"no {REL}/ in this repo — no project memory has been saved here, and this step never "
              f"creates any")
        return 1
    if seen.unreadable or seen.index_unreadable:
        print("\n".join(refusals(seen, [])))
        return 2
    if not seen.files:
        print(f"{REL}/ was read and holds no memory file — there is nothing whose shape this convention "
              f"governs, and this step never creates any")
        return 1
    fixes, stuck = deviations(seen)
    blocked = refusals(seen, stuck)
    if blocked:
        print("\n".join(blocked))
        print("Resolve those by hand and re-run /adopt for this step, or record n/a if the shape here "
              "is deliberate.")
        return 2
    if fixes:
        print(f"{REL}/{INDEX} holds {len(fixes)} link target(s) that are not a bare filename, each naming "
              f"a file that sits beside it:")
        for fix in fixes:
            print(f"  line {fix.link.line_no}: {fix.link.target} -> {fix.name}")
        return 0
    # Already in the target shape: read off the files themselves rather than inferred from an
    # absence. Verify sees this first in /adopt, so probe answering it is for a direct run and
    # for audit re-deriving an n/a line.
    print(f"already in the target shape: {len(seen.files)} memory file(s) all opening with ---, and "
          f"{len(seen.links)} index link(s) all naming a file beside {INDEX}")
    return 1


def cmd_apply(root: str, dry_run: bool) -> int:
    seen = look(root)
    if not seen.has_dir or not seen.files:
        print(f"no memory file under {REL}/ to bring into shape — whether this repo keeps project memory "
              f"is a question for a human rather than an apply")
        return 3
    fixes, stuck = deviations(seen)
    blocked = refusals(seen, stuck)
    if blocked:
        print("\n".join(blocked))
        print(f"Nothing was written and {REL}/ is untouched — a repo this step cannot bring all the way "
              f"into shape must not be left half-way.")
        return 3
    if not fixes:
        print(f"already in the target shape: {len(seen.files)} memory file(s) all opening with ---, and "
              f"{len(seen.links)} index link(s) all naming a file beside {INDEX}")
        return 0
    updated = rewrite(seen.raw, fixes)
    fresh, problems = parse_index(updated)
    bad = [link for link in fresh if link.kind == "path"]
    if problems or bad or len(fresh) != len(seen.links) or skeleton(updated, fresh) != skeleton(seen.raw, seen.links):
        # The rewritten text is checked before it reaches disk, so a rewrite that would move any
        # byte outside a link target leaves the committed index exactly as it was.
        print(f"the rewritten index does not read back as {len(seen.links)} link(s) with every path-shaped "
              f"target gone, so nothing was written and {REL}/{INDEX} is untouched")
        return 3
    if dry_run:
        for fix in fixes:
            print(f"would rewrite  line {fix.link.line_no}: {fix.link.target} -> {fix.name}")
        print(f"{len(fixes)} of {len(seen.links)} index link(s) would become a bare filename; "
              f"{len(seen.files)} memory file(s) already open with ---")
        return 0
    temp_path = os.path.join(seen.base, TEMP)
    try:
        with open(temp_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        os.replace(temp_path, os.path.join(seen.base, INDEX))
    except OSError as exc:
        print(f"could not write {REL}/{INDEX} ({exc}) — the index is untouched")
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return 3
    after = look(root)
    results = check_each(fixes, after)
    for _, line in results:
        print(line)
    if any(not ok for ok, _ in results):
        return 3
    print(f"{len(fixes)} of {len(seen.links)} index link target(s) in {REL}/{INDEX} rewritten to a bare "
          f"filename, each asserted to name a file beside the index; {len(seen.files)} memory file(s) "
          f"assert as opening with ---")
    return 0


def check_each(fixes: list[Fix], after: Look) -> list[tuple[bool, str]]:
    """One (ok, line) per rewritten target, re-read from disk and asserted individually.

    Per item and never on a tally: a count of bare targets passes the moment one entry is fixed
    and another is mangled, and the index is the only thing pointing at these files
    (learnings/git-stash-pull-safety.md).
    """
    results: list[tuple[bool, str]] = []
    for fix in fixes:
        link = after.links[fix.ordinal] if fix.ordinal < len(after.links) else None
        found = link is not None and link.target == fix.name and fix.name in after.names
        state = "ok        " if found else "NOT IN SHAPE"
        results.append((found, f"{state}  {fix.link.target} -> {link.target if link else '<gone>'}"))
    return results


def cmd_verify(root: str) -> int:
    """Is this repo in the shape the convention requires — never, did a rewrite run here.

    The shape is re-derived from disk every time, which is what makes `audit` a real re-check: a
    repo that conformed when its line was written and has since gained an index entry copied from
    the global one fails here rather than passing on the strength of the record.
    """
    seen = look(root)
    if not seen.has_dir:
        print(f"no {REL}/ to read, so whether this repo's memory files carry frontmatter and its index "
              f"names them by bare filename is not a shape this script can observe")
        return 2
    if seen.unreadable or seen.index_unreadable:
        print("\n".join(refusals(seen, [])))
        return 2
    if not seen.files:
        print(f"{REL}/ holds no memory file — there is no shape here to assert, and a pass on an empty "
              f"directory could not tell a conforming repo from one nobody looked at")
        return 2
    fixes, stuck = deviations(seen)
    failures = refusals(seen, stuck)
    failures += [f"line {fix.link.line_no}: {fix.link.target} is not a bare filename ({fix.name} sits "
                 f"beside the index)" for fix in fixes]
    if failures:
        print("\n".join(failures))
        return 3
    print(f"{len(seen.files)} memory file(s) under {REL}/, each opening with ---, and {len(seen.links)} "
          f"link(s) in {INDEX}, each naming a file beside it")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
