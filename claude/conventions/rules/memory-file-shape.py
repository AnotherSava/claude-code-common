"""Every project memory file opens with frontmatter, and every index entry names a bare filename.

Project memory is a directory of markdown files plus a `MEMORY.md` index beside them. Two things
make it readable by anything other than the person who wrote it: each file opens with a `---` block
saying what the memory is, and each index entry links to a sibling by bare filename. The global
index in `CLAUDE.md` describes the same files from a different directory and so uses
`~/.claude/memory/<file>.md`; markdown never expands `~`, so a line copied from one index into the
other is a link that resolves to nothing.

The shape is re-derived from disk on every run, which is what makes this a continuous rule rather
than a migration: a repo that conformed the day it adopted and has since gained an index entry
copied from the global one fails here.

A repo with no `.claude/memory/` holds vacuously, and so does one whose directory is empty. That is
the right answer for a check a commit gate runs — there is no file here whose shape this governs,
and refusing instead would fail the gate of every repo that keeps no project memory. Whether the
directory *should* exist is the memory-cache-symlink convention's question, not this one's.

What cannot be read raises rather than passing: a memory file that will not open as text, an index
that will not, a directory that will not list. A transcrypt-encrypted memory in a locked repo reads
as base64 rather than as a `---` block, which surfaces here as a missing frontmatter line and is
worth naming in the finding rather than leaving a reader to guess.
"""

import os
import re
from typing import NamedTuple

REL = ".claude/memory"
INDEX = "MEMORY.md"

# A markdown link, with the target as group 1. An angle-bracketed target and a trailing "title" are
# both matched so that neither reads as a shape this parser cannot classify.
LINK_RE = re.compile(r"\[[^\]\r\n]*\]\((<[^>\r\n]*>|[^()\s]*)(?:[ \t]+\"[^\"\r\n]*\")?\)")
OPENER_RE = re.compile(r"\]\(")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


class Unreadable(Exception):
    """Something that is there and would not read, so the shape here was never established.

    Distinct from absence, which is an answer: no memory directory means there is no file whose
    shape this governs, while a memory file that will not open as text means the one thing this rule
    asserts about it is unknown.
    """


class Link(NamedTuple):
    target: str  # as written, between ( and )
    line_no: int
    kind: str    # "bare" · "path" · "other" — the third names no file beside the index


class Look(NamedTuple):
    files: list[str]          # every memory file under the directory, index excluded
    no_frontmatter: list[str]
    has_index: bool
    links: list[Link]
    problems: list[str]       # `](` shapes the parser could not read as a link, verbatim
    names: set[str]           # the files sitting beside the index, which is what a bare link may name


def read_text(path: str, shown: str) -> str:
    """A file's text with its line endings untranslated. Raises when it cannot be read.

    `newline=""` so a CRLF index is read as it sits on disk rather than through the platform's
    translation, since these repos are shared between a Windows machine and a macOS one. The name
    to put in a failure is passed in, so a refusal names the file the way a finding would rather
    than by a path that is this machine's alone.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{shown} could not be read as UTF-8 text ({exc})") from exc


def first_line(path: str, shown: str) -> str:
    """The file's opening line. Raises when it cannot be read as text at all."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readline()
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{shown} could not be read as UTF-8 text ({exc})") from exc


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

    An http or mailto target is a reference to something outside the directory and is read as such
    rather than failed; a `file:` one is a machine-specific absolute path, which committed
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

    Report rather than skip: a target this reader cannot classify is plausibly a path-shaped one,
    and quietly walking past it would call an index bare while one entry never was.
    """
    links: list[Link] = []
    openers: set[int] = set()
    for match in LINK_RE.finditer(raw):
        start = match.start(1)
        openers.add(start - 2)
        links.append(Link(match.group(1), line_of(raw, start), classify(match.group(1))))
    # Column as well as line: two unreadable link openers on one line would otherwise print the same
    # sentence twice, and a report a reader cannot tell apart is a report they skim.
    problems = [f"line {line_of(raw, m.start())} column {column_of(raw, m.start())}: {line_text(raw, m.start())}"
                for m in OPENER_RE.finditer(raw) if m.start() not in openers]
    return links, problems


def look(root: str) -> Look:
    """Everything this rule reads, gathered once."""
    base = os.path.join(root, *REL.split("/"))
    if not os.path.isdir(base):
        return Look([], [], False, [], [], set())
    files: list[str] = []
    no_frontmatter: list[str] = []
    # Walked unfiltered, and deliberately: this walks `.claude/memory/` rather than the repo, and
    # the gitignore-unhides-committed rule asserts that exact path is not ignored. A repo running
    # this rule has adopted that one too — the record is a single integer and the versions are
    # contiguous — so there is no hidden file here for a git filter to find.
    for parent, dirs, names in os.walk(base):
        dirs[:] = sorted(name for name in dirs if name != ".git")
        for name in sorted(names):
            if not name.lower().endswith(".md") or name == INDEX:
                continue
            rel = os.path.relpath(os.path.join(parent, name), base).replace(os.sep, "/")
            files.append(rel)
            if first_line(os.path.join(parent, name), f"{REL}/{rel}").lstrip("\ufeff").strip() != "---":
                no_frontmatter.append(rel)  # a BOM is Notepad's, not a missing block
    index_path = os.path.join(base, INDEX)
    has_index = os.path.isfile(index_path)
    links, problems = parse_index(read_text(index_path, f"{REL}/{INDEX}") if has_index else "")
    try:
        names = {name for name in os.listdir(base) if os.path.isfile(os.path.join(base, name))}
    except OSError as exc:
        raise Unreadable(f"{REL}/ would not list ({exc}), so which files an index entry may name "
                         f"is unknown") from exc
    return Look(files, no_frontmatter, has_index, links, problems, names)


def link_faults(seen: Look) -> list[str]:
    """Every index entry that does not name a file sitting beside the index.

    "Exactly one file carries that basename" is satisfied by construction: the candidates are the
    files sitting beside the index, and a directory cannot hold two entries under one name. A target
    whose basename is not among them — an entry pointing at a doc elsewhere in the repo, or at a
    file since renamed — is named as its own finding, because which of those it is decides the fix.
    """
    faults: list[str] = []
    for link in seen.links:
        if link.kind == "other":
            continue
        name = basename_of(link.target)
        here = f"{REL}/{INDEX} line {link.line_no}"
        if link.kind == "bare" and name not in seen.names:
            faults.append(f"{here}: the index names {link.target}, and no such file sits beside it")
        elif link.kind == "path" and name in seen.names:
            faults.append(f"{here}: {link.target} is not a bare filename ({name} sits beside the index)")
        elif link.kind == "path":
            faults.append(f"{here}: {link.target} is not a bare filename, and no {name} sits beside the index")
    return faults


def check(root: str) -> list[str]:
    """Every memory file or index entry out of shape, one line each."""
    seen = look(root)
    faults = [f"{REL}/{rel} does not open with a --- block saying what the memory is (a "
              f"transcrypt-encrypted memory reads as base64 until the repo is unlocked)"
              for rel in seen.no_frontmatter]
    if seen.files and not seen.has_index:
        faults.append(f"{len(seen.files)} memory file(s) under {REL}/ with no {INDEX} beside them — writing "
                      f"the index means summarising each memory in a line, which is a human's sentence")
    faults += [f"{REL}/{INDEX} holds a shape this rule cannot read as a link, {problem}"
               for problem in seen.problems]
    return faults + link_faults(seen)
