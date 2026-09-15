#!/usr/bin/env python3
"""Deterministic backlog helper for the /memo skill.

One memo is one file, so a memo can be as long as the idea needs without any of
it being squeezed onto a checklist line. Open and done are directories, not a
marker inside a file, so listing the backlog never parses a status:

    <repo>/.claude/memos/<slug>.md        an open memo
    <repo>/.claude/memos/done/<slug>.md   a memo that has been addressed

Each file is a `created:` frontmatter block, an `# H1` title, and optional body:

    ---
    created: 2026-09-12 05:17:22
    ---

    # Improve memos by storing in separate files

    Body prose, as long as it needs to be.

Frontmatter carries the sort key rather than the filename, so a future ordering
(priority, area) is a new field instead of renaming every file on disk.

  memos.py add [--title T] "<text>"   write a new open memo; title derived if absent
  memos.py list [--width N]           numbered, newest-first, wrapped + aligned titles
  memos.py show <n|slug>              one memo in full, title and body
  memos.py path <n|slug>              its absolute path, for editing it directly
  memos.py done <n|slug> [<n|slug>…]  move them into done/, resolved before any move
  memos.py reopen <n|slug> […]        move them back out of done/ (n indexes done/)
  memos.py drop <n|slug> […]          delete open memos outright
  memos.py prune                      delete every done memo
  memos.py count                      "<open> open · <done> done"

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
CREATED_RE = re.compile(r"^created:[ \t]*(.+?)[ \t]*$", re.M)
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

    @property
    def stamp(self) -> str:
        """The capture time as shown to a reader — seconds are for sorting only."""
        return self.created[:STAMP_LEN]


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


def _parse(path: str, done: bool) -> Memo:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    created, rest = "", raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 3)
        if end != -1:
            match = CREATED_RE.search(raw[4:end])
            created, rest = (match.group(1) if match else ""), raw[end + 5:]
    lines = rest.lstrip("\n").splitlines()
    head = lines[0] if lines else ""
    title = head[2:].strip() if head.startswith("# ") else head.strip()
    return Memo(path, os.path.splitext(os.path.basename(path))[0], created, title, "\n".join(lines[1:]).strip("\n"), done)


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


def _slug(title: str, taken: set[str]) -> str:
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
    slug, n = base, 2
    while slug.casefold() in folded:
        slug, n = f"{base}-{n}", n + 1
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


def _write_memo(slug: str, created: str, title: str, body: str) -> str:
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
            fh.write(f"---\ncreated: {created}\n---\n\n# {title}\n")
            if body:
                fh.write(f"\n{body}\n")
    except FileExistsError:
        sys.exit(f"refusing to overwrite {os.path.basename(path)} — a memo already holds that slug")
    return path


def add(text: str, title: str | None = None) -> Memo:
    """Create one open memo — the single writer, shared by the CLI and by anything importing this."""
    body = text.strip()
    if not title:
        title, body = _split_title(text)
    if not title:
        sys.exit("memo text required")
    slug = _slug(title, {m.slug for m in _load()})
    created = datetime.datetime.now().strftime(TS_FMT)
    return Memo(_write_memo(slug, created, title, body), slug, created, title, body, False)


def _take_flag(args: list[str], name: str) -> str | None:
    """Remove `--name value` from args in place and return the value."""
    if name not in args:
        return None
    i = args.index(name)
    value = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    return value


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


def _move(memo: Memo, directory: str) -> str:
    """Move a memo between open and done, returning the slug it now has.

    The slug is re-derived against the destination, so it can differ from the one the
    memo arrived with — which is why the caller must print this rather than `memo.slug`.
    """
    os.makedirs(directory, exist_ok=True)
    slug = _slug(memo.title, {m.slug for m in _load() if m.done != memo.done})
    os.replace(memo.path, os.path.join(directory, f"{slug}.md"))
    return slug


def cmd_add(args: list[str]) -> None:
    title = _take_flag(args, "--title")
    # Joined but never `.split()` — collapsing whitespace here once turned a memo quoting
    # `tr -d '\n'` into `tr -d ' '`, silently (see learnings/unicode-escapes-in-tool-input.md).
    memo = add(" ".join(args), title=title)
    # Echo the stored title: it is the one part that gets normalised, so this is the last
    # moment a mangled shell fragment or escape is still visible.
    print(f"{memo.title}\n{os.path.relpath(memo.path, _root())}")
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
        # subsequent_indent matches the prefix's character width, so continuation lines
        # line up under the title on the first line (textwrap counts the em-dash as 1).
        print(textwrap.fill(label, width=width, initial_indent=prefix, subsequent_indent=" " * len(prefix)))


def cmd_show(args: list[str]) -> None:
    memo = _select(args)
    print(f"{memo.stamp} — {memo.title}")
    if memo.body:
        print(f"\n{memo.body}")


def cmd_path(args: list[str]) -> None:
    print(_select(args).path)


def cmd_done(args: list[str]) -> None:
    done_dir = _dirs()[1]
    for memo in _select_all(args):
        # Name the undo at the one moment it might be wanted, using the slug the memo has
        # NOW: a number indexes the open list it has just left, and its slug can change on
        # the way into done/ when something there already holds it.
        print(f"done: {memo.title}\nundo: memos.py reopen {_move(memo, done_dir)}")
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


def cmd_prune(args: list[str]) -> None:
    done = [m for m in _load() if m.done]
    for memo in done:
        os.remove(memo.path)
    print(f"pruned {len(done)} done memo{'' if len(done) == 1 else 's'}")
    cmd_count([])


def cmd_count(args: list[str]) -> None:
    memos = _load()
    print(f"{sum(1 for m in memos if not m.done)} open · {sum(1 for m in memos if m.done)} done")


def _refuse_if_format_unadopted() -> None:
    """Stop before touching a backlog whose format this repo has not adopted yet.

    This layout is defined by a convention in the dotfiles repo, and every command here reads it
    as though it were already true. In a repo still on the format a convention step replaces,
    that is wrong in both directions: `list` and `count` report an empty backlog while the old
    file holds items, and `add` writes a memo beside it, producing the half-migrated state the
    step then refuses to resolve on its own. Measured against a copy of one repo's real backlog:
    one `memo` call put eleven items on the wrong side of a migration that had not happened.

    The question asked is the version, not the artifact — `has this repo adopted the newest step
    affecting memo?` rather than `does memos.md still exist?`. The second answers for one
    migration and has to be rewritten for the next; the first keeps working when the format moves
    again, because the next step declares `affects: memo` and this check needs no edit.

    It never blocks on its own failure. An adopt skill that is missing, moved or unreadable makes
    the answer unknown, not bad, and a backlog helper that refuses to run because a sibling skill
    is broken is worse than one that writes a memo in a repo that turned out to be behind — so
    that path says so on stderr and continues. Being behind is also already reported once per
    session by `conventions-check.py`, which is the surface that catches the read side: this
    refusal covers the command line, and that notice covers the status bar.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "adopt"))
    try:
        import conventions
        behind = conventions.behind_for(_root(), "memo")
    except BaseException as exc:
        print(f"note: could not check whether this repo has adopted the memo format ({exc})", file=sys.stderr)
        return
    if behind is None:
        return
    through, required, title = behind
    sys.exit(f"This repo has not adopted the memo backlog format: it is at v{through}, and v{required} "
             f"({title}) is what defines the layout every command here reads.\n"
             f"Run /adopt first — writing a memo now would leave the backlog half migrated.")


def main() -> None:
    cmd, *rest = (sys.argv[1:] or ["list"])
    handlers = {"add": cmd_add, "list": cmd_list, "show": cmd_show, "path": cmd_path,
                "done": cmd_done, "reopen": cmd_reopen, "drop": cmd_drop,
                "prune": cmd_prune, "count": cmd_count}
    handler = handlers.get(cmd)
    if not handler:
        sys.exit(f"usage: memos.py {{{'|'.join(handlers)}}}")
    _refuse_if_format_unadopted()
    handler(rest)


if __name__ == "__main__":
    main()
