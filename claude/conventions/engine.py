#!/usr/bin/env python3
"""The convention engine: the versions on one side, a repo's one-integer record on the other.

    python engine.py versions                  every version: number, title, rules
    python engine.py status <repo-root>        where this repo stands
    python engine.py adopt <repo-root> <n>     write the record

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
# in the fork's own repos, `status` and `adopt` refuse to touch them, and `behind_for` waves every
# tool through a repo it can no longer speak for.
OWNER = "AnotherSava"

FOLDER_RE = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)[ \t]*$")
# ` #` opens a trailing comment, as it does in the YAML this block is written to look like — a
# reader that kept them would turn `rules: node-engines   # optional` into a rule name with no file.
COMMENT_RE = re.compile(r"[ \t]+#.*$")
NAME_RE = re.compile(r"^[a-z0-9-]+$")
ORIGIN_URL_RE = re.compile(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$")
# Everything a version's frontmatter may declare. Anything else is refused rather than ignored: a
# `version:` or `script:` left behind by a port would otherwise sit there reading as authoritative
# while the folder name and the folder's contents quietly decided both.
FIELDS = ("title", "affects", "rules")

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
    affects: tuple[str, ...]  # tools whose stored data this reshapes — see `behind_for`
    rules: tuple[str, ...]    # continuous rules this version hands to the checker
    folder: str
    readme: str
    apply: str                # the optional mechanical migration, "" when the prose is the whole of it


class Record(NamedTuple):
    number: int         # the committed record's integer; 0 when there is no file
    present: bool       # whether the file exists — "never asked" is not "at 0"
    exempt: str         # the reason, when a record line reads `exempt <reason>`
    error: str          # the full sentence to print when the file will not parse


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
    script = os.path.join(folder, "apply.py")
    return Version(int(match.group(1)), match.group(2), title, _names(data, "affects", label, "tool name"),
                   _names(data, "rules", label, "rule name"), folder, readme, script if os.path.isfile(script) else "")


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


def _read_one(path: str) -> tuple[int, bool, str, str]:
    """(number, the file exists, exempt reason, error sentence) for one record file.

    Only a missing file reads as "no record". Every other way of failing to read one — a
    permission bit, a half-written file, bytes that are not UTF-8 — is an error sentence, because
    "the file is not there" and "the file is there and could not be read" are different facts and
    the second one silently rewinds the repo to v0: the next `adopt` would walk it from the start.
    `utf-8-sig` because Notepad and PowerShell's `Out-File` write a BOM, which would otherwise land
    as a parse error pointing at the header comment.
    """
    rel = ".claude/" + os.path.basename(path)
    try:
        with open(path, encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        return 0, False, "", ""
    except (OSError, UnicodeDecodeError) as exc:
        return 0, True, "", f"{rel} could not be read ({exc})."
    content = [(number, text) for number, text in ((n, raw.strip()) for n, raw in enumerate(lines, 1))
               if text and not text.startswith("#")]
    if not content:
        return 0, True, "", f"{rel} holds no content line: it must carry a version number or an exempt line."
    if len(content) > 1:
        where = ", ".join(str(number) for number, _ in content)
        return 0, True, "", (f"{rel} holds {len(content)} content lines (lines {where}), and the record is "
                             f"exactly one: which of them this repo stands on is not recoverable.")
    number, text = content[0]
    if text.split()[0] == "exempt":
        reason = text[len("exempt"):].strip()
        if not reason:
            return 0, True, "", f"{rel} could not be parsed (line {number}): an exempt line must name its reason."
        return 0, True, reason, ""
    if not text.isdigit():
        return 0, True, "", (f"{rel} could not be parsed (line {number}): {text!r} is neither a version number "
                             f"nor an exempt line.")
    return int(text), True, "", ""


def read_record(root: str) -> Record:
    """The record file for `root`, read once. The only reader of it anywhere."""
    return Record(*_read_one(os.path.join(root, *RECORD_REL.split("/"))))


def parse_error_message(record: Record) -> str:
    """The sentence shown when a record file will not parse — one wording, every caller."""
    return f"{record.error} Conventions state is unknown — /adopt will not run until it is fixed."


def adopted(root: str) -> int:
    """The version this repo has adopted. An exempt repo and one with no file both read as 0.

    Those two are different facts from each other and from a plain 0, and `read_record` is where
    the difference lives; a caller that only wants "which rules is this repo entitled to" wants
    this number. An unreadable record raises instead of reading as 0, because 0 would send a walk
    back to the first version in a repo that may have run all of them.
    """
    record = read_record(root)
    if record.error:
        raise RecordError(parse_error_message(record))
    return record.number


def _pending(versions: list[Version], record: Record) -> list[Version]:
    return [] if record.exempt else [version for version in versions if version.number > record.number]


def pending(root: str) -> list[Version]:
    """Every version this repo has yet to adopt, ascending. Empty for an exempt repo."""
    record = read_record(root)
    if record.error:
        raise RecordError(parse_error_message(record))
    return _pending(load_versions(), record)


def behind_for(root: str, tool: str) -> tuple[int, int, str] | None:
    """`(adopted, required, title)` when this repo has not adopted the newest version reshaping
    `tool`'s stored data, else None.

    A tool that reads a format these conventions define cannot trust that format until the repo
    has adopted the version that last changed it. Asking "does the old artifact still exist?" is
    the wrong question — it answers for one migration and has to be rewritten for the next — so a
    version declares `affects:` instead and the tool asks for a number.

    Real case: v1 turns `.claude/memos.md` into `.claude/memos/`, and `memos.py` reads only the
    new layout. In a repo that has not adopted v1, `list` reports an empty backlog while
    thirty-three items sit in the old file, and `add` writes a memo into a directory beside it,
    producing the half-migrated state v1 then refuses to resolve on its own.

    None means "go ahead", and it is returned for a repo this system does not govern — no `.git`,
    a third-party origin, an `exempt` line — because a tool must not refuse to work in a directory
    that was never going to hold a record. Anything that stops this from reaching an answer raises
    instead, so a caller can tell a pass from a question never put.
    """
    if not is_repo(root) or is_third_party(root) is not None:
        return None
    wanted = [version for version in load_versions() if tool in version.affects]
    if not wanted:
        return None
    record = read_record(root)
    if record.error or record.exempt:
        return None
    required = max(version.number for version in wanted)
    if record.number >= required:
        return None
    return record.number, required, next(v.title for v in wanted if v.number == required)


def _write_number(path: str, number: int) -> str:
    """Write the record file: the comments it already carries, or the header, then the integer.

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
        handle.write("\n".join([*(comments or RECORD_HEADER), str(number)]) + "\n")
    return path


def write_record(root: str, number: int) -> list[str]:
    """Move this repo's record to `number`, returning the files written.

    The number only ever moves forward, one at a time, and never past the newest version in this
    checkout. One at a time is what keeps the record from claiming a migration nobody read: a walk
    that jumps to the newest number would leave every version under it recorded as run on the
    strength of nothing.
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
    if number <= record.number:
        raise RecordError(f"this repo is already at v{record.number}: the record moves forward only, and a lower "
                          f"number would claim migrations were undone that were not")
    if number != record.number + 1:
        raise RecordError(f"refusing to skip from v{record.number} to v{number}: a walk advances one version at a "
                          f"time, so every number in between is one somebody read")
    written = [_write_number(os.path.join(root, *RECORD_REL.split("/")), number)]
    return [os.path.relpath(path, root).replace(os.sep, "/") for path in written]


# ---------------------------------------------------------------- whose repo this is


def is_repo(root: str) -> bool:
    """Whether a record written here would be tracked by anything. A worktree's `.git` is a file."""
    return os.path.exists(os.path.join(root, ".git"))


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


def _origin_owner(root: str) -> str | None:
    """The account owning `origin`, read out of `.git/config` as text. None when there is none.

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
            elif section == '[remote"origin"]' and stripped.split("=")[0].strip().casefold() == "url":
                match = ORIGIN_URL_RE.search(stripped.split("=", 1)[1].strip())
                return match.group(1) if match else None
        return None
    return None


def is_third_party(root: str) -> str | None:
    """The owner's name when this repo belongs to someone else, else None."""
    owner = _origin_owner(root)
    return owner if owner is not None and owner.casefold() != OWNER.casefold() else None


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


def _listing(version: Version) -> str:
    rules = f"  [rules: {', '.join(version.rules)}]" if version.rules else ""
    return f"  v{version.number:<3} {version.slug:<28} {version.title}{rules}"


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
    if record.number > newest:
        # The hook says this too, but its systemMessage never reaches the transcript, so /adopt
        # reads the gap from here. Without this line a repo recorded against a newer version set
        # reads as current, and the walk runs against a version list older than the record.
        print(f"this record names v{record.number}, above the newest version in this dotfiles checkout "
              f"(v{newest}): pull the dotfiles repo before adopting anything here")
    waiting = _pending(versions, record)
    print(f"{len(waiting)} version(s) pending")
    for version in waiting:
        print(_listing(version))
    return 0


def cmd_adopt(root: str, raw: str) -> int:
    if not raw.lstrip("v").isdigit():
        print(f"{raw!r} is not a version number")
        return 2
    number = int(raw.lstrip("v"))
    try:
        written = write_record(root, number)
    except (VersionError, RecordError) as exc:
        print(exc)
        return 2
    for path in written:
        print(f"recorded v{number} in {path}")
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
    return _usage("{versions|status|adopt}")


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
