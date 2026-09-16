#!/usr/bin/env python3
"""Deterministic backlog helper for the /memo skill.

One memo is one file, so a memo can be as long as the idea needs without any of
it being squeezed onto a checklist line. Open and done are directories, not a
marker inside a file, so listing the backlog never parses a status:

    <repo>/.claude/memos/<slug>.md                  an open memo
    <repo>/.claude/memos/done/<date>-<slug>.md      one that has been addressed

Each file is a frontmatter block, an `# H1` title, and an optional body. The
frontmatter carries `created:`, and optionally a `platform:` binding the memo to
the box that can act on it — absent means either machine, which almost all are:

    ---
    created: 2026-09-12 05:17:22
    platform: windows
    ---

    # Improve memos by storing in separate files

    Body prose, as long as it needs to be.

An open memo's filename is a slug and nothing else: frontmatter carries its sort
key, so a future ordering (priority, area) is a new field rather than a rename of
every file on disk.

Closing prefixes the close date onto the name, which is the one place that rule
is deliberately inverted. `done/` is append-only and no command lists it — `list`
and `show` both resolve against the open backlog — so its only reader is a file
browser, `ls` or `git status`, and a name is the only thing those sort by. The
cost is the usual one and is accepted here: a second ordering over done memos
would mean renaming them all. Nothing reads the date back, so it is stored once,
in the name, rather than also in a field that could disagree with it.

  memos.py add [--title T] [--platform P] "<text>"
                                      write a new open memo; title derived if absent
  memos.py list [--width N]           numbered, newest-first, wrapped + aligned titles
  memos.py show <n|slug>              one memo in full, title and body
  memos.py path <n|slug>              its absolute path, for editing it directly
  memos.py done <n|slug> [<n|slug>…]  move them into done/, resolved before any move
  memos.py reopen <n|slug> […]        move them back out of done/ (n indexes done/)
  memos.py drop <n|slug> […]          delete open memos outright
  memos.py count                      "<open> open · <done> done", plus how many of the
                                      open ones this machine's platform cannot act on

The root is the git toplevel, else the current directory. `memos-surface.py`
imports `open_memos()` from here rather than re-implementing the parse.
"""
import datetime
import functools
import os
import re
import shutil
import subprocess
import sys
import textwrap
import unicodedata
from typing import NamedTuple

# Emit UTF-8 regardless of the platform console codepage, so the em-dash survives (Windows defaults
# stdout to cp1252, which would mangle it).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Seconds are stored but never shown: several memos captured in one minute (a /wrap-up disposing
# of a batch) would otherwise tie, and the tie-break would order them by slug, not capture order.
TS_FMT = "%Y-%m-%d %H:%M:%S"  # local timezone, 24-hour
STAMP_LEN = len("2026-09-12 21:51")
# The close date a memo takes on its way into done/. Date and not a timestamp: the name exists to
# make a directory listing read in order, and several memos closed in one `done 2 4` share a day
# anyway — the within-day order is what `_slug`'s `-2` suffix settles, not something to encode.
DONE_DATE_FMT = "%Y-%m-%d"
CREATED_RE = re.compile(r"^created:[ \t]*(.+?)[ \t]*$", re.M)
# A memo may name the platform that can act on it, for the minority whose work simply cannot be
# done from the other box. Absence means either machine, so an unbound backlog — which is most of
# it — writes and renders byte-identical to before. `os_label()` in the github-status skill maps
# the same two boxes and is deliberately not shared: that one returns a display label for a report
# ("macOS"), this one a stored token that goes in a committed file, and its module is far too heavy
# to import from the hook path `memos-surface.py` runs on.
#
# A platform names a platform, not a box: the day a second mac exists, `macos` means either of
# them. That is over-broad and visible in the listing rather than silently wrong, and the fix is
# one entry here plus a separate `host:` field — which stays free precisely because this key is
# named for what it holds.
PLATFORMS = ("macos", "windows")
THIS_PLATFORM = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
PLATFORM_RE = re.compile(r"^platform:[ \t]*(.+?)[ \t]*$", re.M)
TITLE_MAX = 90
# A title ends at the first spaced en/em dash, or where a sentence closes and a new one opens.
# The lookbehind requires a word character before the period so `hosts/<host>/.env — X` and
# `v1.2 of the thing` are not mistaken for sentence ends. A line break is handled separately.
BREAK_RE = re.compile(r"[ \t]+[–—][ \t]+|(?<=[\w)\"'][.!?])[ \t]+(?=[A-Z(\"'])")
# Windows refuses these as filenames whatever the extension.
RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


class Memo(NamedTuple):
    path: str
    slug: str
    created: str
    title: str
    body: str
    done: bool
    platform: str

    @property
    def stamp(self) -> str:
        """The capture time as shown to a reader — seconds are for sorting only."""
        return self.created[:STAMP_LEN]

    @property
    def tag(self) -> str:
        """The marker a listing puts in front of the title, empty for an unbound memo."""
        return f"[{self.platform}] " if self.platform else ""

    @property
    def elsewhere(self) -> bool:
        """Bound to a platform that is not the one running — the work cannot finish here."""
        return bool(self.platform) and self.platform != THIS_PLATFORM


@functools.lru_cache(maxsize=1)
def _root() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    return os.getcwd()


def _dirs(root: str | None = None) -> tuple[str, str]:
    """The open and done directories for `root`, defaulting to this process's repo.

    Callers that already know the root pass it, so no `git` subprocess runs — the
    status-line hook refreshes every couple of seconds and must not spawn one.
    """
    base = os.path.join(root or _root(), ".claude", "memos")
    return base, os.path.join(base, "done")


def _field(block: str, pattern: re.Pattern) -> str:
    """One frontmatter value, or `""` when the key is absent. Keys are read individually rather
    than through a general parser, so an unrecognised one stays on disk and out of the model."""
    match = pattern.search(block)
    return match.group(1) if match else ""


def _parse(path: str, done: bool) -> Memo:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    created, platform, rest = "", "", raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 3)
        if end != -1:
            block, rest = raw[4:end], raw[end + 5:]
            created = _field(block, CREATED_RE)
            # Folded on the way in, so a hand-edited `platform: Windows` reads as the same binding
            # `add` would have written. An unknown value is kept verbatim rather than dropped: it
            # renders in every listing, which is how a typo gets noticed instead of silently
            # meaning "either machine".
            platform = _field(block, PLATFORM_RE).casefold()
    lines = rest.lstrip("\n").splitlines()
    head = lines[0] if lines else ""
    title = head[2:].strip() if head.startswith("# ") else head.strip()
    body = "\n".join(lines[1:]).strip("\n")
    return Memo(path, os.path.splitext(os.path.basename(path))[0], created, title, body, done, platform)


def _load(root: str | None = None) -> list[Memo]:
    memos = []
    for directory, done in zip(_dirs(root), (False, True)):
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in sorted(names):
            path = os.path.join(directory, name)
            # The extension is folded for the same reason `_slug` folds the stem: a hand-made
            # `Case-Test.MD` that this test skipped stayed out of the `taken` set, and
            # `_move`'s `os.replace` — which has no exclusive mode to fall back on — then
            # overwrote it. Measured on NTFS, exit 0, the memo gone.
            if name.lower().endswith(".md") and os.path.isfile(path):
                memos.append(_parse(path, done))
    return memos


def _newest_first(memos: list[Memo]) -> list[Memo]:
    # Newest `created` first, ties broken by slug ascending. Two memos can only tie when
    # captured in the same second — a batch — where their relative order carries no meaning.
    # An unparseable `created` sorts oldest rather than crashing the listing.
    return sorted(sorted(memos, key=lambda m: m.slug), key=lambda m: m.created, reverse=True)


def open_memos(root: str | None = None) -> list[Memo]:
    """The open backlog, newest first — the numbering every caller shows the user."""
    return _newest_first([m for m in _load(root) if not m.done])


def _slug(title: str, taken: set[str], prefix: str = "") -> str:
    """The filename stem for `title`, unique against `taken`, behind an optional `prefix`.

    The prefix is part of what uniqueness is tested on, never something a caller bolts on
    afterwards: `taken` holds whole stems, so testing the bare slug against them would find
    no clash at all and hand back a name `os.replace` then writes over. Two memos with the
    same title closed on different days do not collide, which is the point of testing the
    prefixed form rather than deduplicating titles across the whole of done/.
    """
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    base = ""
    for word in re.findall(r"[a-z0-9]+", plain.lower()):
        if base and len(base) + 1 + len(word) > 60:
            break
        base = f"{base}-{word}" if base else word
    base = base or "memo"
    if base in RESERVED:
        base = f"{base}-memo"
    # Fold the case before testing membership. APFS and NTFS resolve filenames
    # case-insensitively, so a case-sensitive test hands back a slug the filesystem
    # then opens onto an existing memo — measured, and it destroyed the file it hit.
    folded = {s.casefold() for s in taken}
    slug, n = f"{prefix}{base}", 2
    while slug.casefold() in folded:
        slug, n = f"{prefix}{base}-{n}", n + 1
    return slug


def _split_title(text: str) -> tuple[str, str]:
    """Derive a one-line title, never losing a character of `text`.

    A natural break makes the head the title and the tail the body. Without one,
    a short memo is all title, and a long one keeps its full text in the body so
    the elided words stay readable.
    """
    text = text.strip()
    # A line break is the author saying where the first thought ends, so it wins at any length.
    if "\n" in text:
        head, tail = text.split("\n", 1)
        if head.strip():
            return " ".join(head.split()), tail.strip()
    match = BREAK_RE.search(text, 0, TITLE_MAX + 40)
    if match and match.start() >= 12:
        return " ".join(text[:match.start()].split()), text[match.end():].strip()
    if len(text) <= TITLE_MAX:
        return " ".join(text.split()), ""
    cut = text.rfind(" ", 0, TITLE_MAX)
    return " ".join(text[:cut if cut > 0 else TITLE_MAX].split()) + "…", text


def _write_memo(slug: str, created: str, title: str, body: str, platform: str = "") -> str:
    """Write one memo file into the open backlog — a memo is only ever created open."""
    memo_dir, _ = _dirs()
    os.makedirs(memo_dir, exist_ok=True)
    path = os.path.join(memo_dir, f"{slug}.md")
    # "x" rather than "w": every caller arrives with a slug that is supposed to be free, so
    # an existing file means the slug logic was wrong and writing would destroy a memo. The
    # backstop matters because the filesystem, not this code, decides what counts as a clash.
    # newline="\n" keeps the committed file LF on Windows too, so the two machines
    # sharing these repos never see a whole-file line-ending diff.
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            # The platform line is written only when set, so an unbound memo is byte-identical to
            # one written before this field existed.
            fh.write(f"---\ncreated: {created}\n")
            if platform:
                fh.write(f"platform: {platform}\n")
            fh.write(f"---\n\n# {title}\n")
            if body:
                fh.write(f"\n{body}\n")
    except FileExistsError:
        sys.exit(f"refusing to overwrite {os.path.basename(path)} — a memo already holds that slug")
    return path


def add(text: str, title: str | None = None, platform: str = "") -> Memo:
    """Create one open memo — the single writer, shared by the CLI and by anything importing this."""
    body = text.strip()
    if not title:
        title, body = _split_title(text)
    if not title:
        sys.exit("memo text required")
    # Validated here rather than in `cmd_add` because this is the single writer: an importer gets
    # the same refusal, and a mistyped token never reaches a file every reader would then render
    # verbatim for months. Refusing before `_write_memo` leaves nothing behind to clean up.
    platform = platform.casefold()
    if platform and platform not in PLATFORMS:
        sys.exit(f"unknown platform {platform!r} — one of: {', '.join(PLATFORMS)}")
    slug = _slug(title, {m.slug for m in _load()})
    created = datetime.datetime.now().strftime(TS_FMT)
    return Memo(_write_memo(slug, created, title, body, platform), slug, created, title, body, False, platform)


def _take_flag(args: list[str], name: str) -> str | None:
    """Remove a leading `--name value` pair from args in place and return the value.

    Only the opening run of `--flag value` pairs is searched. Scanning the whole list took the
    flag word out of a memo's own prose along with the word after it — `memo use --title to name
    a thing` lost two words, silently — and every flag added widened that. Callers put their
    flags first, which both shell wrappers and every `add` call site in the skills already do.
    """
    i = 0
    while i + 1 < len(args) and args[i].startswith("--"):
        if args[i] == name:
            value = args[i + 1]
            del args[i:i + 2]
            return value
        i += 2
    return None


def _resolve(key: str, memos: list[Memo], noun: str) -> Memo:
    if key.isdigit():
        n = int(key)
        if not 1 <= n <= len(memos):
            sys.exit(f"no {noun} memo {n} ({len(memos)} {noun})")
        return memos[n - 1]
    # Exact case, then folded, then as a substring. The middle rung reaches a memo whose file
    # differs only in case from the name a listing handed back; the first keeps two such memos
    # separately addressable where the filesystem does distinguish them.
    key_low = key.lower()
    hits = ([m for m in memos if m.slug == key]
            or [m for m in memos if m.slug.lower() == key_low]
            or [m for m in memos if key_low in m.slug.lower()])
    if not hits:
        sys.exit(f"no {noun} memo matching {key!r}")
    if len(hits) > 1:
        sys.exit("ambiguous, matches: " + ", ".join(m.slug for m in hits))
    return hits[0]


def _select_all(args: list[str], done: bool = False) -> list[Memo]:
    """Resolve every number or slug against ONE listing, before any of them moves.

    Numbers index the same newest-first order the caller just printed, so they only mean
    anything within one turn — and only until the first memo moves, since closing one
    renumbers the rest. Taking the whole batch against a single snapshot is what makes
    `done 2 4` act on what it names. A slug is stable either way, and is what the undo
    hints hand back.
    """
    if not args:
        sys.exit("a memo number or slug is required")
    noun = "done" if done else "open"
    memos = _newest_first([m for m in _load() if m.done]) if done else open_memos()
    picked: list[Memo] = []
    for key in args:
        memo = _resolve(key, memos, noun)
        # One memo named twice (as a number and as its slug) is one memo — and skipping the
        # repeat keeps the second reference off a file the first has already moved.
        if memo.path not in {m.path for m in picked}:
            picked.append(memo)
    return picked


def _select(args: list[str]) -> Memo:
    """Resolve a single number or slug, for the commands that act on one memo.

    Extras are refused rather than dropped: their siblings take a list now, so obeying the
    first half of `show 2 4` would be the reading a caller cannot check.
    """
    if len(args) > 1:
        sys.exit("one memo number or slug, not several")
    return _select_all(args)[0]


def _move(memo: Memo, directory: str, prefix: str = "") -> str:
    """Move a memo between open and done, returning the slug it now has.

    The slug is re-derived from the title against the destination, so it can differ from the
    one the memo arrived with — which is why the caller must print this rather than
    `memo.slug`. Re-deriving is also what strips a close-date prefix on the way back out:
    reopening starts from the title again, so nothing has to recognise or remove the date.
    """
    os.makedirs(directory, exist_ok=True)
    slug = _slug(memo.title, {m.slug for m in _load() if m.done != memo.done}, prefix)
    os.replace(memo.path, os.path.join(directory, f"{slug}.md"))
    return slug


def cmd_add(args: list[str]) -> None:
    title = _take_flag(args, "--title")
    platform = _take_flag(args, "--platform") or ""
    # Joined but never `.split()` — collapsing whitespace here once turned a memo quoting
    # `tr -d '\n'` into `tr -d ' '`, silently (see learnings/unicode-escapes-in-tool-input.md).
    memo = add(" ".join(args), title=title, platform=platform)
    # Echo the stored title and tag: they are the parts that get normalised, so this is the last
    # moment a mangled shell fragment or escape is still visible.
    print(f"{memo.tag}{memo.title}\n{os.path.relpath(memo.path, _root())}")
    cmd_count([])


def _width(args: list[str]) -> int:
    if "--width" in args:
        i = args.index("--width")
        try:
            return int(args[i + 1])
        except (IndexError, ValueError):
            pass
    # stdout is almost always piped here (the skill's `!` capture, or the Bash tool), so this returns
    # the fallback, not the real terminal. Callers detect the width themselves and pass --width — same
    # split as the github-status skill.
    return shutil.get_terminal_size((100, 24)).columns


def cmd_list(args: list[str]) -> None:
    width, memos = _width(args), open_memos()
    if not memos:
        print("(no open memos)")
        return
    numw = len(str(len(memos)))
    for i, memo in enumerate(memos, 1):
        prefix = f"{str(i).rjust(numw)}. {memo.stamp} — "
        # `…` means "there is more to read than this line", and `show` prints it. A title that
        # had to be elided already ends in one, so don't append a second and make both meaningless.
        label = memo.title if not memo.body or memo.title.endswith("…") else f"{memo.title} …"
        # The tag heads the label rather than the prefix, so the stamp column stays flush and the
        # indent arithmetic below is untouched. A leading bracketed token also looks nothing like
        # the trailing ` …` that already means "more to read" — two markers, two shapes.
        # subsequent_indent matches the prefix's character width, so continuation lines
        # line up under the title on the first line (textwrap counts the em-dash as 1).
        print(textwrap.fill(f"{memo.tag}{label}", width=width, initial_indent=prefix, subsequent_indent=" " * len(prefix)))


def cmd_show(args: list[str]) -> None:
    memo = _select(args)
    print(f"{memo.stamp} — {memo.tag}{memo.title}")
    if memo.body:
        print(f"\n{memo.body}")


def cmd_path(args: list[str]) -> None:
    print(_select(args).path)


def cmd_done(args: list[str]) -> None:
    done_dir = _dirs()[1]
    # One date for the whole batch, read once: `done 2 4` closes both memos in the same act, and
    # a per-memo read could straddle midnight and file them under two different days.
    prefix = f"{datetime.datetime.now().strftime(DONE_DATE_FMT)}-"
    for memo in _select_all(args):
        # Name the undo at the one moment it might be wanted, using the slug the memo has
        # NOW: a number indexes the open list it has just left, and its slug gains the close
        # date on the way into done/ — so the name to reopen by is never the one just listed.
        print(f"done: {memo.title}\nundo: memos.py reopen {_move(memo, done_dir, prefix)}")
    cmd_count([])


def cmd_reopen(args: list[str]) -> None:
    open_dir = _dirs()[0]
    for memo in _select_all(args, done=True):
        print(f"reopened: {memo.title}\nslug: {_move(memo, open_dir)}")
    cmd_count([])


def cmd_drop(args: list[str]) -> None:
    for memo in _select_all(args):
        os.remove(memo.path)
        print(f"dropped: {memo.title}")
    cmd_count([])


def cmd_count(args: list[str]) -> None:
    memos = _load()
    # A subset of the open count, not a filter of it — nothing anywhere hides a memo bound
    # elsewhere. It is said here because `count` is printed alone as the /memo skill's Context
    # line and after every mutating command, where no listing is on screen to carry the tags.
    elsewhere = sum(1 for m in memos if not m.done and m.elsewhere)
    note = f" ({elsewhere} not for {THIS_PLATFORM})" if elsewhere else ""
    print(f"{sum(1 for m in memos if not m.done)} open · {sum(1 for m in memos if m.done)} done{note}")


def _refuse_if_format_unadopted() -> None:
    """Stop before touching a backlog whose format this repo has not adopted yet.

    This layout is defined by a convention in the dotfiles repo, and every command here reads it
    as though it were already true. In a repo still on the format a convention version replaces,
    that is wrong in both directions: `list` and `count` report an empty backlog while the old
    file holds items, and `add` writes a memo beside it, producing the half-migrated state the
    migration then refuses to resolve on its own. Measured against a copy of one repo's real
    backlog: one `memo` call put eleven items on the wrong side of a migration that had not
    happened.

    The question asked is the version, not the artifact — `has this repo adopted the newest
    version affecting memo?` rather than `does memos.md still exist?`. The second answers for one
    migration and has to be rewritten for the next; the first keeps working when the format moves
    again, because the next version declares `affects: memo` and this check needs no edit.

    It never blocks on its own failure. A conventions engine that is missing, moved or unreadable
    makes the answer unknown, not bad, and a backlog helper that refuses to run because a sibling
    tool is broken is worse than one that writes a memo in a repo that turned out to be behind —
    so that path says so on stderr and continues. Being behind is also already reported once per
    session by `conventions-check.py`, which is the surface that catches the read side: this
    refusal covers the command line, and that notice covers the status bar.
    """
    # Through realpath, because this file is reached as a symlink under ~/.claude and the engine
    # it needs sits in the dotfiles checkout the link points into, not beside the link.
    dotfiles = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    sys.path.insert(0, os.path.join(dotfiles, "conventions"))
    try:
        import engine
        behind = engine.behind_for(_root(), "memo")
    except BaseException as exc:
        print(f"note: could not check whether this repo has adopted the memo format ({exc})", file=sys.stderr)
        return
    if behind is None:
        return
    adopted, required, title = behind
    sys.exit(f"This repo has not adopted the memo backlog format: it is at v{adopted}, and v{required} "
             f"({title}) is what defines the layout every command here reads.\n"
             f"Run /adopt first — writing a memo now would leave the backlog half migrated.")


def main() -> None:
    cmd, *rest = (sys.argv[1:] or ["list"])
    handlers = {"add": cmd_add, "list": cmd_list, "show": cmd_show, "path": cmd_path,
                "done": cmd_done, "reopen": cmd_reopen, "drop": cmd_drop, "count": cmd_count}
    handler = handlers.get(cmd)
    if not handler:
        sys.exit(f"usage: memos.py {{{'|'.join(handlers)}}}")
    _refuse_if_format_unadopted()
    handler(rest)


if __name__ == "__main__":
    main()
