#!/usr/bin/env python3
"""The convention engine: the versions on one side, a repo's one-integer record on the other.

    python engine.py versions                  every version: number, title, rules
    python engine.py status <repo-root>        where this repo stands
    python engine.py adopt <repo-root> <n>     write the record
    python engine.py decline <repo-root> <n> <reason>   decline an optional version, in a fork

One module owns both halves because every other surface asks one of them a question — the
`/adopt` skill, the session-start notice, `memos.py`, the cross-machine status report — and a
second reader of either format drifts from the first the day one of them changes.

The record is one integer, not a line per version, because a version is a migration: it ran in
this repo or it did not, and the number says how far. The ledger this replaces carried a state
per version, and two of its three states recorded an *exception* to a convention — a repo saying
"this one does not apply to me". An exception belongs in the convention, evaluated against the
repo in front of it every time, not remembered once in a file nobody re-reads; the third state
let an underspecified convention sit declined while the repos around it diverged. What has to
hold *continuously* is not in this file at all: the checker beside it runs the rules a repo's
number entitles it to, on every commit, which is the only place a standing property can be
asserted without someone remembering to ask.

A fork is the one place a per-repo exception is recorded, and the convention still decides where
one is allowed. A fork tracks a project someone else owns, and how closely it should stay to that
project is the fork's own judgement rather than anything a file in it can show: a Node pin or a
LICENSE the upstream never asked for turns every pull from upstream into a merge. So a version
whose frontmatter says `optional: forks` may be declined in a repo `fork_of` recognises, and the
record carries a `decline <n> <reason>` line for it beside the number. Every version not marked
that way is required in a fork exactly as anywhere else. Both conditions are checked when the line
is written; once written it travels with the repo, as an `exempt` line does (see `read_record`).

A version's number and its slug come from its folder name and are stored nowhere else, so the
two can never disagree. The sequence has been renumbered exactly once, when the memory-cache
migration stopped being a version at all and became a universal rule: every number above it
moved down one, and the records naming them were rewritten by hand. Treat that as the cost of
retiring a version rather than as a routine — a number in a commit message or a transcript older
than that change points at a different migration.

Exit codes, shared with the checker: 0 ok · 1 a rule was violated or a walk found work · 2 the
tool refuses and a human has to fix something. Nothing in this file returns 1: being behind is
the normal answer to `status`, not a failure of it.

No YAML and no third-party imports: PyYAML is not in the standard library, and the session-start
hook imports this module under `python -S`.
"""

from __future__ import annotations

import os
import re
import sys
from typing import NamedTuple, TextIO

HERE = os.path.dirname(os.path.realpath(__file__))
VERSIONS_DIR = os.path.join(HERE, "versions")
# <repo>/claude/conventions -> <repo>. `realpath` above resolves the ~/.claude/conventions symlink,
# so this is the checkout even when the module was reached through the installed path.
REPO = os.path.dirname(os.path.dirname(HERE))

RECORD_REL = ".claude/conventions"
# Whose repos adopt these conventions. A clone of someone else's project is exempt with no opt-out
# file anywhere — see `~/.claude/memory/user_github_account.md`. A fork of these dotfiles has to
# change this name, and three things go quiet if it does not: the session-start notice says nothing
# in the fork's own repos, `status` and `adopt` refuse to touch them, and `behind` waves every
# tool through a repo it can no longer speak for.
OWNER = "AnotherSava"

FOLDER_RE = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)[ \t]*$")
# ` #` opens a trailing comment, as it does in the YAML this block is written to look like — a
# reader that kept them would turn `rules: node-engines   # optional` into a rule name with no file.
COMMENT_RE = re.compile(r"[ \t]+#.*$")
NAME_RE = re.compile(r"^[a-z0-9-]+$")
# The owner is the first path segment of a hosted remote — `[user@]host:owner/repo` or
# `scheme://host/owner/repo` — and nothing else. A local path or a `file://` URL names a directory,
# not an account, and reading its parent folder as one made `C:/work/other` a fork of `work`.
# The scp-like form needs a host of two characters or more, as git's own drive-prefix check does, so
# `C:/work` stays a path while an SSH alias such as `gh-work:owner/repo` still names its owner.
REMOTE_URL_RE = re.compile(r"^(?:(?!file:)[a-z][a-z0-9+.-]*://(?:[^@/]+@)?[^/]+/|(?:[^@/:]+@)?[^@/:\\]{2,}:)"
                           r"([^/]+)/[^/].*?(?:\.git)?/?$", re.IGNORECASE)
# Everything a version's frontmatter may declare. Anything else is refused rather than ignored: a
# `version:` or `script:` left behind by a port would otherwise sit there reading as authoritative
# while the folder name and the folder's contents quietly decided both.
FIELDS = ("title", "rules", "optional")
# The values `optional:` may take. A fork is the only kind of repo that may decline a version, and a
# third-party clone adopts nothing at all, so there is no second value yet.
OPTIONAL_FOR = ("forks",)

RECORD_HEADER = ("# Convention version this repo has adopted, from the claude dotfiles repo.",
                 "# Written by /adopt. See claude/conventions/ in that repo.")


class VersionError(Exception):
    """A version set that cannot be read at all — a folder name that does not parse, a gap.

    Raised rather than returned because every caller's answer is the same: stop. A duplicate
    number in particular must never resolve to a silent winner, since `latest` is derived from
    the set and two folders sharing a number make every "N versions behind" claim arbitrary.
    """


class RecordError(Exception):
    """A record that will not parse, or a number this engine refuses to write.

    Both carry the sentence a human has to act on, and both reach a caller the same way: a
    function that answers with a number raises rather than returning one, because every number
    it could return here — 0 above all — is a claim about the repo that nobody established.
    """


class Version(NamedTuple):
    number: int
    slug: str
    title: str
    rules: tuple[str, ...]    # continuous rules this version hands to the checker
    folder: str
    readme: str
    apply: str                # the optional mechanical migration, "" when the prose is the whole of it
    fork_optional: bool       # `optional: forks` — a fork may decline it


class Record(NamedTuple):
    number: int         # the committed record's integer; 0 when there is no file
    present: bool       # whether the file exists — "never asked" is not "at 0"
    exempt: str         # the reason, when a record line reads `exempt <reason>`
    error: str          # the full sentence to print when the file will not parse
    declined: dict[int, str] = {}   # version -> reason, for each `decline` line; only a fork has any


# ---------------------------------------------------------------- the versions


def _frontmatter(handle: TextIO, label: str) -> dict[str, str]:
    """The `---` block at the head of a README, as flat `key: value` pairs.

    Only the head is read, so the session-start hook pays for a few hundred bytes per version
    rather than the whole of its prose. A line inside the block that is neither blank, a comment,
    nor a `key: value` pair aborts instead of being skipped: a mistyped `rules : node-engines` that
    parses to nothing would otherwise drop a rule out of the set with no message anywhere.
    """
    if handle.readline().strip() != "---":
        raise VersionError(f"{label} does not open with a --- frontmatter block")
    data: dict[str, str] = {}
    for line in handle:
        text = line.rstrip("\r\n")
        if text.strip() == "---":
            return data
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        match = FIELD_RE.match(text)
        if not match:
            raise VersionError(f"{label} frontmatter holds a line this reader cannot classify: {text!r}")
        value = COMMENT_RE.sub("", match.group(2)).strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[match.group(1).casefold()] = value
    raise VersionError(f"{label} frontmatter has no closing ---")


def _read_frontmatter(path: str, label: str) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return _frontmatter(handle, label)
    except OSError as exc:
        raise VersionError(f"{label} could not be read ({exc.strerror})") from exc
    except UnicodeDecodeError as exc:
        raise VersionError(f"{label} is not valid UTF-8 ({exc.reason})") from exc


def _names(data: dict[str, str], key: str, label: str, kind: str) -> tuple[str, ...]:
    names = tuple(part.strip() for part in data.get(key, "").split(",") if part.strip())
    for name in names:
        if not NAME_RE.match(name):
            raise VersionError(f"{label} declares {key}: {name!r}; a {kind} is lowercase letters, digits and dashes")
    return names


def _version_from(name: str) -> Version:
    match = FOLDER_RE.match(name)
    if not match:
        raise VersionError(f"{name!r} is not a version folder: the name is NNN-slug, NNN zero-padded to three digits")
    folder = os.path.join(VERSIONS_DIR, name)
    readme = os.path.join(folder, "README.md")
    label = f"{name}/README.md"
    data = _read_frontmatter(readme, label)
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        raise VersionError(f"{label} frontmatter declares {', '.join(unknown)}; a version carries only "
                           f"{', '.join(FIELDS)}, because its number and slug come from the folder name and "
                           f"its migration script from the folder's contents")
    title = data.get("title", "")
    if not title:
        raise VersionError(f"{label} declares no title")
    optional = data.get("optional", "")
    if optional and optional not in OPTIONAL_FOR:
        raise VersionError(f"{label} declares optional: {optional!r}; the only value is {', '.join(OPTIONAL_FOR)}")
    script = os.path.join(folder, "apply.py")
    return Version(int(match.group(1)), match.group(2), title, _names(data, "rules", label, "rule name"), folder, readme, script if os.path.isfile(script) else "", optional == "forks")


def load_versions() -> list[Version]:
    """Every version in this checkout, ascending.

    A duplicate or a gap is a hard stop rather than a set with a hole in it: `latest` is the last
    number in this list and the record is a claim to have run everything at or below its own
    number, so both readings are wrong the moment the sequence is not 1..N.
    """
    try:
        names = sorted(n for n in os.listdir(VERSIONS_DIR) if os.path.isdir(os.path.join(VERSIONS_DIR, n)))
    except OSError as exc:
        raise VersionError(f"no readable versions directory at claude/conventions/versions ({exc.strerror})") from exc
    versions = sorted((_version_from(name) for name in names), key=lambda v: v.number)
    seen: dict[int, str] = {}
    for version in versions:
        if version.number in seen:
            raise VersionError(f"v{version.number} is declared twice: {seen[version.number]} and {version.slug}")
        seen[version.number] = version.slug
    numbers = [version.number for version in versions]
    if numbers != list(range(1, len(numbers) + 1)):
        raise VersionError(f"version numbers must run from 1 with no gaps; this checkout holds {numbers}")
    return versions


def latest() -> int:
    """The newest version in this checkout, 0 when there are none."""
    versions = load_versions()
    return versions[-1].number if versions else 0


def dotfiles_sha() -> str:
    """The short sha of this dotfiles checkout, read from .git without forking.

    Every message that claims a "latest" version names this, so the claim is always qualified by
    the checkout it was derived from — the two machines are routinely at different commits, and a
    behind checkout reporting a repo as current is the one wrong answer this system must not give.
    """
    git_dir = os.path.join(REPO, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()
    except OSError:
        return "unknown"
    if not head.startswith("ref:"):
        return head[:7] or "unknown"
    ref = head.split(":", 1)[1].strip()
    try:
        with open(os.path.join(git_dir, *ref.split("/")), encoding="utf-8") as handle:
            return handle.read().strip()[:7] or "unknown"
    except OSError:
        pass
    try:
        with open(os.path.join(git_dir, "packed-refs"), encoding="utf-8") as handle:
            for line in handle:
                sha, _, name = line.partition(" ")
                if name.strip() == ref:
                    return sha[:7]
    except OSError:
        pass
    return "unknown"


# ---------------------------------------------------------------- the record


def _read_one(path: str) -> Record:
    """The record file at `path`, parsed but not yet checked against the repo or the version set.

    Only a missing file reads as "no record". Every other way of failing to read one — a
    permission bit, a half-written file, bytes that are not UTF-8 — is an error sentence, because
    "the file is not there" and "the file is there and could not be read" are different facts and
    the second one silently rewinds the repo to v0: the next `adopt` would walk it from the start.
    `utf-8-sig` because Notepad and PowerShell's `Out-File` write a BOM, which would otherwise land
    as a parse error pointing at the header comment.

    The first content line is the number or the exempt line. Every line after it must be a
    `decline <n> <reason>`, below or at the number and named once; anything else is an error,
    because a second number would leave which one this repo stands on unrecoverable.
    """
    rel = ".claude/" + os.path.basename(path)

    def broken(sentence: str) -> Record:
        return Record(0, True, "", sentence, {})

    try:
        with open(path, encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        return Record(0, False, "", "", {})
    except (OSError, UnicodeDecodeError) as exc:
        return broken(f"{rel} could not be read ({exc}).")
    content = [(number, text) for number, text in ((n, raw.strip()) for n, raw in enumerate(lines, 1))
               if text and not text.startswith("#")]
    if not content:
        return broken(f"{rel} holds no content line: it must carry a version number or an exempt line.")
    (number, text), rest = content[0], content[1:]
    if text.split()[0] == "exempt":
        reason = text[len("exempt"):].strip()
        if not reason:
            return broken(f"{rel} could not be parsed (line {number}): an exempt line must name its reason.")
        if rest:
            return broken(f"{rel} could not be parsed (line {rest[0][0]}): an exempt record carries nothing "
                          f"after its exempt line, since an exempt repo adopts nothing to decline.")
        return Record(0, True, reason, "", {})
    if not text.isdigit():
        return broken(f"{rel} could not be parsed (line {number}): {text!r} is neither a version number "
                      f"nor an exempt line.")
    adopted = int(text)
    declined: dict[int, str] = {}
    for line, extra in rest:
        parts = extra.split(None, 2)
        if parts[0] != "decline":
            return broken(f"{rel} could not be parsed (line {line}): {extra!r} is not a decline line, and the "
                          f"record holds one number — which of two this repo stands on is not recoverable.")
        if len(parts) < 3 or not parts[1].isdigit():
            return broken(f"{rel} could not be parsed (line {line}): a decline line reads `decline <version> "
                          f"<reason>`, and the reason is mandatory.")
        version = int(parts[1])
        if version in declined:
            return broken(f"{rel} could not be parsed (line {line}): v{version} is declined twice.")
        if not 1 <= version <= adopted:
            return broken(f"{rel} could not be parsed (line {line}): v{version} is declined, but the record "
                          f"stands at v{adopted} and a version is declined only when the walk reaches it.")
        declined[version] = parts[2].strip()
    return Record(adopted, True, "", "", declined)


def read_record(root: str) -> Record:
    """The record file for `root`, read once. The only reader of it anywhere.

    A decline line is checked for its own shape here and nowhere else at read time. Whether the repo
    is a fork and whether the version offered the choice are settled when the line is written,
    because neither can be re-derived from the repo alone: the `upstream` remote lives in each
    clone's own `.git/config`, so a fresh clone of the fork has none, and the version set is
    whatever this machine's dotfiles checkout holds, which is routinely behind the other one. Read
    against either, a decline the repo made would turn into a broken record on the other machine.
    So a decline travels with the repo, as an `exempt` line does.
    """
    return _read_one(os.path.join(root, *RECORD_REL.split("/")))


def parse_error_message(record: Record) -> str:
    """The sentence shown when a record file will not parse — one wording, every caller."""
    return f"{record.error} Conventions state is unknown — /adopt will not run until it is fixed."


def _pending(versions: list[Version], record: Record) -> list[Version]:
    return [] if record.exempt else [version for version in versions if version.number > record.number]


def pending(root: str) -> list[Version]:
    """Every version this repo has yet to adopt, ascending. Empty for an exempt repo."""
    record = read_record(root)
    if record.error:
        raise RecordError(parse_error_message(record))
    return _pending(load_versions(), record)


def behind(root: str, required: int) -> tuple[int, str] | None:
    """`(adopted, title)` when this repo has not adopted version `required`, else None.

    A tool that reads a format these conventions define cannot trust that format until the repo
    has adopted the version that last changed it. The caller names the number it needs, beside the
    code that reads the format — which is where anyone changing that format is already working.
    Asking "does the old artifact still exist?" instead answers for one migration and has to be
    rewritten for the next.

    Real case: v1 turns `.claude/memos.md` into `.claude/memos/`, and `memos.py` reads only the
    new layout. In a repo that has not adopted v1, `list` reports an empty backlog while
    thirty-three items sit in the old file, and `add` writes a memo into a directory beside it,
    producing the half-migrated state v1 then refuses to resolve on its own.

    A fork that declined `required` gets the same answer as a repo below it: the format that
    version defines was never adopted there.

    None means "go ahead", and it is returned only for a repo this system does not govern — no
    `.git`, a third-party origin, an `exempt` line — because a tool must not refuse to work in a
    directory that was never going to hold a record. Anything that stops this from reaching an
    answer raises, including a record that will not parse: a caller has to be able to tell a pass
    from a question never put, and silence on an unreadable record is the second dressed as the
    first.
    """
    if not is_repo(root) or is_third_party(root) is not None:
        return None
    record = read_record(root)
    if record.error:
        raise VersionError(record.error)
    if record.exempt or (record.number >= required and required not in record.declined):
        return None
    version = next((v for v in load_versions() if v.number == required), None)
    return record.number, version.title if version else f"v{required}"


def _write_number(path: str, number: int, declined: dict[int, str]) -> str:
    """Write the record file: the comments it already carries, or the header, the integer, then one
    `decline` line per declined version, ascending.

    The comments are kept rather than regenerated because they are the file's own statement of
    what its one line means, and a repo that has annotated them should not lose that to a bump.
    `newline="\\n"` so the committed record never shows up as a whole-file line-ending diff between
    the two machines, and a trailing newline so the next bump is a one-line diff.
    """
    try:
        with open(path, encoding="utf-8-sig") as handle:
            comments = [line.rstrip("\r\n") for line in handle if line.lstrip().startswith("#")]
    except OSError:
        comments = []
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        declines = [f"decline {version} {declined[version]}" for version in sorted(declined)]
        handle.write("\n".join([*(comments or RECORD_HEADER), str(number), *declines]) + "\n")
    return path


def write_record(root: str, number: int, decline: str | None = None) -> list[str]:
    """Move this repo's record to `number`, returning the files written.

    The number only ever moves forward, one at a time, and never past the newest version in this
    checkout. One at a time is what keeps the record from claiming a migration nobody read: a walk
    that jumps to the newest number would leave every version under it recorded as run on the
    strength of nothing.

    With `decline`, the same step records the version as declined for that reason instead of
    performed, which only a fork may do and only for a version marked `optional: forks`. A version
    already declined is the one number allowed at or below the record: adopting it then says its
    migration has now been performed, so its decline line goes and the number stays where it is.
    """
    versions = load_versions()
    if not is_repo(root):
        raise RecordError("conventions cannot be recorded here: this is not a git repo, so the record would be "
                          "a file nothing tracks and no clone ever sees")
    other = is_third_party(root)
    if other is not None:
        raise RecordError(f"this repo's origin belongs to {other}, not {OWNER}: nothing is recorded in a clone "
                          f"of someone else's project")
    record = read_record(root)
    if record.error:
        raise RecordError(parse_error_message(record))
    if record.exempt:
        raise RecordError(f"this repo is exempt — {record.exempt}. Nothing is recorded here.")
    newest = versions[-1].number if versions else 0
    if number > newest:
        raise RecordError(f"v{number} is above the newest version in this dotfiles checkout (v{newest}): pull the "
                          f"dotfiles repo before recording it here")
    path = os.path.join(root, *RECORD_REL.split("/"))
    declined = dict(record.declined)
    if number in declined:
        if decline is not None:
            raise RecordError(f"v{number} is already declined here — {declined[number]}")
        del declined[number]
        return [os.path.relpath(_write_number(path, record.number, declined), root).replace(os.sep, "/")]
    if number <= record.number:
        raise RecordError(f"this repo is already at v{record.number}: the record moves forward only, and a lower "
                          f"number would claim migrations were undone that were not")
    if number != record.number + 1:
        raise RecordError(f"refusing to skip from v{record.number} to v{number}: a walk advances one version at a "
                          f"time, so every number in between is one somebody read")
    if decline is not None:
        reason = " ".join(decline.split())
        version = next(v for v in versions if v.number == number)
        if fork_of(root) is None:
            raise RecordError(f"only a fork may decline a version — a repo whose `upstream` remote belongs to "
                              f"someone other than {OWNER} — so v{number} is adopted here or the walk stops")
        if not version.fork_optional:
            raise RecordError(f"v{number} ({version.title}) is required in a fork too: its README does not say "
                              f"`optional: forks`")
        if not reason:
            raise RecordError("a decline names its reason, so the fork's judgement is readable in the record")
        declined[number] = reason
    return [os.path.relpath(_write_number(path, number, declined), root).replace(os.sep, "/")]


# ---------------------------------------------------------------- whose repo this is


def is_repo(root: str) -> bool:
    """Whether a record written here would be tracked by anything. A worktree's `.git` is a file."""
    return os.path.exists(os.path.join(root, ".git"))


def repo_root(start: str) -> str | None:
    """The nearest ancestor of `start` holding a `.git`, or None. A worktree's `.git` is a file."""
    current = os.path.abspath(start)
    while True:
        if is_repo(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _git_directory(root: str) -> str | None:
    """Where this checkout's git metadata lives. A worktree's `.git` is a file pointing elsewhere."""
    path = os.path.join(root, ".git")
    if os.path.isdir(path):
        return path
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("gitdir:"):
            target = line.split(":", 1)[1].strip()
            return target if os.path.isabs(target) else os.path.normpath(os.path.join(root, target))
    return None


def _remote_owner(root: str, remote: str) -> str | None:
    """The account owning `remote`, read out of `.git/config` as text. None when there is none.

    None and "someone else" are different answers: a repo with no remote yet is still one of ours
    and still adopts, while a clone of someone else's project never does.

    This lives here rather than in the hook because `/adopt` asks the same question and has to get
    the same answer. It did not: the hook was correctly silent in the `agterm` clone while `status`
    offered to walk thirteen versions there, which ends in a record file committed to a repo that is
    not ours. One predicate, one answer.
    """
    git_dir = _git_directory(root)
    if git_dir is None:
        return None
    wanted = f'[remote"{remote}"]'.casefold()
    # A linked worktree's `.git` file points at `<main>/.git/worktrees/<name>`, which holds no
    # `config` of its own — the remote is two levels up, in the main checkout's `.git`.
    for candidate in (os.path.join(git_dir, "config"),
                      os.path.join(os.path.dirname(os.path.dirname(git_dir)), "config")):
        try:
            with open(candidate, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        section = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                section = stripped.replace(" ", "").casefold()
            elif section == wanted and stripped.split("=")[0].strip().casefold() == "url":
                match = REMOTE_URL_RE.match(stripped.split("=", 1)[1].strip())
                return match.group(1) if match else None
        return None
    return None


def is_third_party(root: str) -> str | None:
    """The owner's name when this repo belongs to someone else, else None."""
    owner = _remote_owner(root, "origin")
    return owner if owner is not None and owner.casefold() != OWNER.casefold() else None


def fork_of(root: str) -> str | None:
    """The upstream owner's name when this repo is a fork, else None.

    A fork is a repo whose `origin` is ours and whose `upstream` remote is someone else's: work is
    committed and pushed here, and pulled from a project another account owns. That is the one
    kind of repo allowed to decline a version marked `optional: forks`. A repo with no origin is
    not a fork whatever its upstream says, since nothing shows it is ours to commit into, and a
    clone whose origin is someone else's is third-party and adopts nothing at all.
    """
    origin = _remote_owner(root, "origin")
    if origin is None or origin.casefold() != OWNER.casefold():
        return None
    upstream = _remote_owner(root, "upstream")
    return upstream if upstream is not None and upstream.casefold() != OWNER.casefold() else None


# ---------------------------------------------------------------- subcommands


def _usage(form: str) -> int:
    print(f"usage: engine.py {form}")
    return 2


def _versions_or_refuse() -> tuple[list[Version], int]:
    try:
        return load_versions(), 0
    except VersionError as exc:
        print(f"version set refused: {exc}")
        return [], 2


def _listing(version: Version, optional_shown: bool = True) -> str:
    rules = f"  [rules: {', '.join(version.rules)}]" if version.rules else ""
    optional = "  [optional for forks]" if optional_shown and version.fork_optional else ""
    return f"  v{version.number:<3} {version.slug:<28} {version.title}{rules}{optional}"


def cmd_versions() -> int:
    versions, bad = _versions_or_refuse()
    if bad:
        return bad
    print(f"{len(versions)} version(s), latest v{versions[-1].number if versions else 0}, dotfiles at {dotfiles_sha()}")
    for version in versions:
        print(_listing(version))
    return 0


def cmd_status(root: str) -> int:
    versions, bad = _versions_or_refuse()
    if bad:
        return bad
    newest = versions[-1].number if versions else 0
    print(f"repo: {root}")
    print(f"latest v{newest} (dotfiles at {dotfiles_sha()})")
    if not is_repo(root):
        # Three real project directories on this machine have no `.git`. Walking the versions there
        # would end in a record file no clone ever sees, reported as written — so the walk stops at
        # the same sentence the session-start notice prints, rather than looking normal.
        print("conventions cannot be recorded here: this is not a git repo")
        return 2
    other = is_third_party(root)
    if other is not None:
        print(f"this repo's origin belongs to {other}, not {OWNER}: it adopts nothing, and the "
              f"session-start notice stays silent here")
        return 2
    record = read_record(root)
    if record.error:
        print(parse_error_message(record))
        return 2
    if record.exempt:
        print(f"exempt — {record.exempt}")
        return 0
    if not record.present:
        print("no record file: this repo has never been asked where it stands")
    else:
        print(f"this repo: v{record.number}")
    upstream = fork_of(root)
    if upstream is not None:
        # /adopt reads this line to know it may offer the decline, so it is printed whether or not
        # anything is pending: a fork with nothing left to walk can still re-adopt a declined version.
        print(f"a fork of {upstream}'s project: a version marked [optional for forks] may be declined here")
    elif record.declined:
        # A fresh clone of a fork has no `upstream` remote, since git never commits one. Its declines
        # still hold, but nothing new can be declined here until the remote is added back.
        print("this record declines versions, but no `upstream` remote owned by someone else is configured "
              "in this clone: add it to be offered a decline for the versions still pending")
    for number in sorted(record.declined):
        print(f"declined v{number}: {record.declined[number]}")
    if record.number > newest:
        # The hook says this too, but its systemMessage never reaches the transcript, so /adopt
        # reads the gap from here. Without this line a repo recorded against a newer version set
        # reads as current, and the walk runs against a version list older than the record.
        print(f"this record names v{record.number}, above the newest version in this dotfiles checkout "
              f"(v{newest}): pull the dotfiles repo before adopting anything here")
    waiting = _pending(versions, record)
    print(f"{len(waiting)} version(s) pending")
    for version in waiting:
        print(_listing(version, upstream is not None))
    return 0


def cmd_adopt(root: str, raw: str, decline: str | None = None) -> int:
    if not raw.lstrip("v").isdigit():
        print(f"{raw!r} is not a version number")
        return 2
    number = int(raw.lstrip("v"))
    try:
        before = read_record(root).declined
        written = write_record(root, number, decline)
    except (VersionError, RecordError) as exc:
        print(exc)
        return 2
    verb = "declined" if decline is not None else "adopted the declined" if number in before else "recorded"
    for path in written:
        print(f"{verb} v{number} in {path}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    command, rest = (args[0] if args else ""), args[1:]
    if command == "versions":
        return cmd_versions()
    if command == "status":
        if len(rest) != 1:
            return _usage("status <repo-root>")
        return cmd_status(os.path.abspath(rest[0]))
    if command == "adopt":
        if len(rest) != 2:
            return _usage("adopt <repo-root> <version>")
        return cmd_adopt(os.path.abspath(rest[0]), rest[1])
    if command == "decline":
        if len(rest) < 3:
            return _usage("decline <repo-root> <version> <reason>")
        return cmd_adopt(os.path.abspath(rest[0]), rest[1], " ".join(rest[2:]))
    return _usage("{versions|status|adopt|decline}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Close to the hooks' never-raise guard, and deliberately not identical to it: a hook owes
        # the harness SystemExit(0) whatever happened, while an engine that exited 0 on a crash
        # would report a record it never wrote. So the traceback goes to stderr, through the
        # interpreter's own hook rather than an import nothing else needs, and the code is the same
        # 2 every other refusal uses — a human has to fix something either way.
        sys.excepthook(*sys.exc_info())
        raise SystemExit(2)
