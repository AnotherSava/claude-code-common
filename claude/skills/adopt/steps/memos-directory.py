#!/usr/bin/env python3
"""v1 — move a repo's .claude/memos.md into .claude/memos/, one file per memo.

The backlog used to be one checklist file and is now one file per memo, so a memo
can be as long as the idea needs and listing one never parses a status. `memos.py`
reads the new layout only, so a repo still holding `memos.md` has a backlog nothing
can list — which is how one repo's sat unnoticed for two days.

Two rules shape everything below, and a failure wrote each of them.

**Every content line is accounted for before anything is deleted.** The first draft
recognised one line shape, silently skipped the rest, and then removed the file,
reporting "each asserted present exactly once" while three items and one memo's
whole body were gone. So the parser classifies every non-blank line as an item, as a
continuation of the item above it, or as the file's own header — and stops on
anything else, naming it verbatim and writing nothing.

**The source goes only after each item has been found again on disk**, in this same
process, matched per item and never on a tally: zero hits means lost, two means
migrated twice, and a count passes the moment one of each happens
(learnings/git-stash-pull-safety.md).

    memos-directory.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    memos-directory.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, source intact
    memos-directory.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the per-item
evidence behind it. The note is one line and carries no tab, because it becomes a
field in a tab-separated record file.
"""

import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from typing import NamedTuple

# The memo skill owns the slug and title logic the write path reuses: `_slug` folds case before
# testing for a clash, which is what stops APFS and NTFS resolving a new memo onto an existing one
# and destroying it. Reached the way `memos-surface.py` reaches the same module, and guarded the
# way the conventions hook guards its engine import — `probe` and `verify` need none of it, so a
# memo skill that has been moved or renamed must not take all three subcommands down with it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "memo"))

import _dispatch  # noqa: E402  — path set above

try:
    from memos import _slug, _split_title
except BaseException:
    _slug = _split_title = None

# Emit UTF-8 whatever the console codepage is. This prints memo text back verbatim, and
# an em-dash through Windows' cp1252 default raises rather than prints — which would
# turn a healthy migration into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OLD = ".claude/memos.md"
# How much of an item's text identifies it when looking for it again on disk. Long enough
# that two memos do not share a prefix, short enough to survive the title/body split.
KEY_LEN = 60

# An item is a bullet at column 0, a checkbox, a date, an optional time, an optional
# separator, then the text. Every part after the date is optional on purpose: the fleet's
# own history holds `- [ ] 2026-06-30: text` with a colon and no time, and `* [ ]` and
# `-  [ ]` both occur. Their meaning is not in doubt, so reading them loses nothing —
# whereas refusing them would send a real backlog back to a human to re-type.
ITEM_RE = re.compile(r"^[-*+][ \t]+\[([ xX])\][ \t]+(\d{4}-\d{2}-\d{2})(?:[ \t]+(\d{2}:\d{2}))?[ \t]*[–—:-]?[ \t]*(.+?)[ \t]*$")
# Any other list line, at any indent. This is the shape that must never be skipped: a
# bullet this script cannot read is plausibly a memo, and guessing either way loses it.
LIST_RE = re.compile(r"^[ \t]*(?:[-*+][ \t]|\d+[.)][ \t])")
HEADING_RE = re.compile(r"^#{1,6}[ \t]")


class Item(NamedTuple):
    done: bool
    created: str  # from the item's own stamp, never from the clock
    text: str
    line_no: int


class Parsed(NamedTuple):
    items: list[Item]
    problems: list[str]  # content lines the parser could not classify, verbatim
    header: list[str]  # the file's own heading and blurb, which the new layout has no place for


class Head(NamedTuple):
    state: str  # "present" · "absent" · "unknown" — the third is git refusing, not a missing file
    text: str
    detail: str


class Write(NamedTuple):
    item: Item
    path: str  # repo-relative, forward slashes, so it reads the same on both machines
    title: str
    body: str
    existing: bool  # already on disk from an earlier half-finished run


def read_text(path: str) -> str | None:
    """A file's text, or None when it cannot be read — no caller here may die on that."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def parse(raw: str) -> Parsed:
    """Classify every line of a pre-migration backlog file: item, continuation, or header.

    A non-blank line directly below an item continues it and is joined with a space, not
    a newline: the old format is one item per line, so a break inside one is an editor's
    wrap, and re-joining it is what hands `_split_title` the sentence the author wrote.
    Prose above the first item is the file's own header — it describes the format being
    retired and is reported by `apply`, never carried into a memo.
    """
    items: list[Item] = []
    problems: list[str] = []
    header: list[str] = []
    in_item = False
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            in_item = False
            continue
        match = ITEM_RE.match(raw_line.rstrip())
        if match:
            flag, date, time, text = match.groups()
            # Seconds match what `memos.py` writes; a date with no time keeps the bare
            # date rather than gaining a 00:00 nobody recorded. Both sort and display.
            items.append(Item(flag != " ", f"{date} {time}:00" if time else date, text, line_no))
            in_item = True
            continue
        structural = bool(LIST_RE.match(raw_line) or HEADING_RE.match(line))
        if in_item and not structural:
            items[-1] = items[-1]._replace(text=f"{items[-1].text} {line}")
            continue
        if not items and not structural:
            header.append(line)
            continue
        if not items and HEADING_RE.match(line):
            header.append(line)
            continue
        problems.append(f"line {line_no}: {raw_line.rstrip()}")
        in_item = False
    return Parsed(stagger_seconds(items), problems, header)


def stagger_seconds(items: list[Item]) -> list[Item]:
    """Give items sharing one minute distinct seconds, in the order the file listed them.

    The old format stamps to the minute, so two memos captured in the same minute arrive with
    identical `created:` values — and `created:` is the only sort key the new format has, since
    the ordering deliberately lives in frontmatter rather than in the filename. Writing both as
    `:00` would therefore discard the one ordering the source file did carry: its line order.

    Measured on the fleet: bga-assistant and printlab each hold exactly one such pair, and the
    hand migration of 2026-09-13 bumped the later item to `:01` for this reason. Reproducing that
    is what lets a re-run through this step rebuild those two backlogs byte for byte.

    Past sixty items in one minute the seconds field runs out and the tail shares `:59`. Nothing
    in this fleet comes close, and refusing the whole migration over it would be the worse answer.
    """
    seen: dict[str, int] = {}
    out: list[Item] = []
    for item in items:
        if not item.created.endswith(":00"):  # a bare date carries no seconds field to stagger
            out.append(item)
            continue
        minute = item.created[:-3]
        index = seen.get(minute, 0)
        seen[minute] = index + 1
        out.append(item._replace(created=f"{minute}:{min(index, 59):02d}"))
    return out


def normalize(text: str) -> str:
    """Case-folded, whitespace-collapsed text with every dash reduced to a space.

    The dash is why this is not a plain casefold: `_split_title` breaks an item at its
    spaced em-dash and the separator does not survive into the written file, so a probe
    that kept it matches nothing. Measured against a real 33-item backlog, where four
    items read as LOST until the dash was dropped.
    """
    plain = unicodedata.normalize("NFKC", text)
    for dash in ("—", "–", "-"):
        plain = plain.replace(dash, " ")
    return " ".join(plain.split()).casefold()


def written_memos(root: str) -> dict[str, str]:
    """Normalised text of every memo file now on disk, keyed by repo-relative path."""
    out: dict[str, str] = {}
    base = os.path.join(root, ".claude", "memos")
    for directory in (base, os.path.join(base, "done")):
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            path = os.path.join(directory, name)
            if name.lower().endswith(".md") and os.path.isfile(path):
                body = read_text(path)
                if body is not None:
                    out[os.path.relpath(path, root).replace(os.sep, "/")] = normalize(body)
    return out


def hits_for(item: Item, written: dict[str, str]) -> list[str]:
    """Every memo file whose text holds this item — the one lookup both apply and verify use."""
    key = normalize(item.text)[:KEY_LEN]
    return [path for path, body in written.items() if key in body]


def check_each(items: list[Item], written: dict[str, str]) -> list[tuple[bool, str]]:
    """One (ok, line) per item, asserted against text and never against a tally.

    Zero hits means the item was lost, two or more that it was migrated twice; a count
    check passes the moment one of each happens, which is why this matches text
    (learnings/git-stash-pull-safety.md).
    """
    results: list[tuple[bool, str]] = []
    for item in items:
        label, found = item.text[:KEY_LEN], hits_for(item, written)
        if len(found) == 1:
            results.append((True, f"ok          {label} -> {found[0]}"))
        else:
            results.append((False, f"{'LOST      ' if not found else 'DUPLICATED'}  {label} -> {found}"))
    return results


def git(root: str, *args: str) -> subprocess.CompletedProcess | None:
    """One git command against `root`, or None when git could not be run at all."""
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def head_backlog(root: str) -> Head:
    """What HEAD carries at the pre-migration path — present, absent, or unanswerable.

    "HEAD has no such file" and "git would not answer" are different facts, and collapsing
    them into one silently skips the per-item assertion: a git refusing with `detected
    dubious ownership` made a repo whose migration was done and uncommitted — the one case
    where that assertion can run at all — report the shape alone and pass.

    A toplevel check guards the read because `git -C <dir>` walks *upward*: run against a
    directory that is not itself a repository, `git show HEAD:.claude/memos.md` answers with
    the *enclosing* repo's file, and the assertion would run against a backlog belonging to
    something else entirely. Compared with `samefile` rather than as strings, since the
    stored spelling of a path and the disk's can differ in case
    (learnings/comparing-paths-symlinks-and-case.md).
    """
    if not os.path.exists(os.path.join(root, ".git")):
        return Head("absent", "", "there is no repository here")
    top = git(root, "rev-parse", "--show-toplevel")
    if top is None:
        return Head("unknown", "", "git could not be run")
    if top.returncode != 0:
        return Head("unknown", "", top.stderr.strip() or f"git rev-parse exited {top.returncode}")
    try:
        if not os.path.samefile(top.stdout.strip(), root):
            return Head("absent", "", "this directory sits inside another repository rather than being one")
    except OSError:
        return Head("unknown", "", f"git named {top.stdout.strip()!r} as the repository root and it could not be compared with this directory")
    # `--verify --quiet` exits 1 on a HEAD that resolves to nothing, which is a repository with no
    # commit yet; a git that is refusing to work on this tree at all exits 128 with its reason.
    head = git(root, "rev-parse", "--verify", "--quiet", "HEAD")
    if head is None:
        return Head("unknown", "", "git could not be run")
    if head.returncode == 128:
        return Head("unknown", "", head.stderr.strip() or "git rev-parse exited 128")
    if head.returncode != 0:
        return Head("absent", "", "this repository has no commit yet")
    shown = git(root, "show", f"HEAD:{OLD}")
    if shown is None:
        return Head("unknown", "", "git could not be run")
    if shown.returncode != 0:
        return Head("absent", "", f"HEAD does not carry {OLD}")
    return Head("present", shown.stdout, "")


def plan_writes(items: list[Item], written: dict[str, str],
                slug_for: Callable[[str, set[str]], str],
                split_title: Callable[[str], tuple[str, str]]) -> tuple[list[Write], list[str]]:
    """Where each item goes, and which ones an earlier run already put there.

    Reusing a file that already holds the item is what makes a half-finished run
    resumable: the alternative — writing it again under `<slug>-2` — creates the exact
    duplicate the per-item assertion exists to catch, and leaves the repo stuck.
    """
    taken = {os.path.splitext(os.path.basename(path))[0] for path in written}
    plan: list[Write] = []
    problems: list[str] = []
    for item in items:
        found = hits_for(item, written)
        title, body = split_title(item.text)
        if len(found) > 1:
            problems.append(f"line {item.line_no} is already under .claude/memos/ twice: {found}")
            continue
        if found:
            plan.append(Write(item, found[0], title, body, True))
            continue
        slug = slug_for(title, taken)
        taken.add(slug)
        folder = ".claude/memos/done" if item.done else ".claude/memos"
        plan.append(Write(item, f"{folder}/{slug}.md", title, body, False))
    return plan, problems


def write_one(root: str, entry: Write) -> None:
    """Write one memo file, stamped from the item rather than from the clock.

    Mode "x" so a half-finished earlier attempt stops this rather than being overwritten;
    newline="\\n" so the two machines sharing these repos never see a whole-file
    line-ending diff.
    """
    path = os.path.join(root, *entry.path.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(f"---\ncreated: {entry.item.created}\n---\n\n# {entry.title}\n")
        if entry.body:
            handle.write(f"\n{entry.body}\n")


def summarise(items: list[Item], reused: int) -> str:
    """The one-line record note — no tab, because it becomes a field in a TSV record."""
    opened = sum(1 for item in items if not item.done)
    note = (f"{len(items)} memos moved out of {OLD} ({opened} open, {len(items) - opened} done); "
            f"each asserted present exactly once")
    return f"{note}; {reused} already under .claude/memos/ and left alone" if reused else note


def report_problems(problems: list[str]) -> None:
    """Name every line the parser could not classify, verbatim, and say what was not done."""
    print(f"{OLD} holds {len(problems)} line(s) this step cannot classify as an item, as a "
          f"continuation of the item above it, or as the file's own header:")
    for problem in problems:
        print(f"  {problem}")
    print(f"Nothing was written and {OLD} is untouched. Put each of those lines into the shape "
          f"`- [ ] YYYY-MM-DD HH:MM — text`, or move it into a memo by hand, then re-run.")


def cmd_probe(root: str) -> int:
    has_old = os.path.isfile(os.path.join(root, OLD))
    written = written_memos(root)
    # A directory holding no memo file is not a migrated backlog: verify fails on exactly that
    # tree, so reading it as "already a directory" would record `n/a — does not apply` for a repo
    # its own verify has just said is not in the target shape. An empty shell is no backlog.
    has_new = bool(written)
    if has_old and not has_new:
        print(f"{OLD} is on disk with no memo file beside it under .claude/memos/")
        return 0
    if has_new and not has_old:
        # Positive evidence read off the disk, not inferred from an absence: the directory
        # is there and the file is not, which is what a finished migration looks like —
        # including one this machine never ran, done on the other and pulled in.
        print(f"already a directory: {len(written)} memo file(s) under .claude/memos/ and no {OLD}")
        return 1
    if has_old and has_new:
        parsed = parse(read_text(os.path.join(root, OLD)) or "")
        print(f"both {OLD} and .claude/memos/ exist — a half-finished migration, and which side is "
              f"authoritative is not this step's guess.")
        if parsed.problems:
            print(f"{OLD} also holds {len(parsed.problems)} line(s) this step cannot classify:")
            for problem in parsed.problems:
                print(f"  {problem}")
        missing = [item for item in parsed.items if not hits_for(item, written)]
        if missing:
            print(f"{len(missing)} of its {len(parsed.items)} items are in {OLD} only and would be "
                  f"lost if it were simply deleted:")
            for item in missing:
                print(f"  line {item.line_no}: {item.text[:KEY_LEN]}")
        else:
            print(f"all {len(parsed.items)} of its items are already under .claude/memos/, so deleting "
                  f"{OLD} by hand loses nothing.")
        print(f"Resolve by hand — delete {OLD} once every item above is under .claude/memos/ — then "
              f"re-run /adopt for this step.")
        return 2
    # No backlog either way. CD4: that is not evidence this repo does not want one, so the
    # question goes to a human. What HEAD says splits it into two different questions.
    head = head_backlog(root)
    if head.state == "present":
        print(f"{OLD} is gone from disk but HEAD still carries it, and no memo file was created — the "
              f"backlog is currently nowhere. Restore it with `git checkout HEAD -- {OLD}` and re-run "
              f"this step, or confirm it was emptied deliberately.")
        return 2
    if head.state == "unknown":
        print(f"git could not be asked what HEAD carries ({head.detail}), so whether a backlog was "
              f"deleted here cannot be told apart from one never kept.")
    shell = " An empty .claude/memos/ is already here holding no memo file, which is a shell rather than a backlog." if os.path.isdir(os.path.join(root, ".claude", "memos")) else ""
    print(f"no backlog either way{'' if head.state == 'unknown' else f', and nothing to restore from HEAD ({head.detail})'}: "
          f"does this repo want a backlog at all? This step never creates one, because an empty "
          f".claude/memos/ is cruft.{shell} Record n/a if the absence is deliberate.")
    return 2


def assert_against_head(raw: str, written: dict[str, str], lead: str) -> int:
    """Assert a committed pre-migration list item by item against what is on disk now.

    This is the only assertion that can run in a repo whose migration is done but not yet
    committed — HEAD still holds the file the working tree deleted, which makes those
    repos the best-verified case rather than a refusal. A line in HEAD the parser cannot
    classify is not asserted, and an unasserted line must never read as a passed one.
    """
    parsed = parse(raw)
    if parsed.problems:
        print(f"HEAD:{OLD} holds {len(parsed.problems)} line(s) this step cannot classify, so they "
              f"were never asserted:")
        for problem in parsed.problems:
            print(f"  NOT ASSERTED  {problem}")
        return 3
    results = check_each(parsed.items, written)
    for _, line in results:
        print(line)
    if any(not ok for ok, _ in results):
        return 3
    print(f"{lead}: {len(parsed.items)} item(s) in HEAD:{OLD}, each asserted present exactly once "
          f"under .claude/memos/")
    return 0


def cmd_apply(root: str, dry_run: bool) -> int:
    old_path = os.path.join(root, OLD)
    raw = read_text(old_path)
    if raw is None:
        return apply_already_done(root)
    parsed = parse(raw)
    if parsed.problems:
        report_problems(parsed.problems)
        return 3
    if not parsed.items:
        print(f"{OLD} holds no checklist line at all, so there is no backlog to move and an empty "
              f".claude/memos/ would be cruft. Whether to delete the file is a human's call.")
        return 3
    if _slug is None or _split_title is None:
        print(f"the memo skill's memos.py could not be imported, and this step reuses its slug and "
              f"title logic rather than re-deriving it — {OLD} is untouched")
        return 3
    written = written_memos(root)
    plan, clashes = plan_writes(parsed.items, written, _slug, _split_title)
    if clashes:
        print("\n".join(clashes))
        print(f"{OLD} is untouched — two memo files holding one item has to be resolved by hand.")
        return 3
    reused = sum(1 for entry in plan if entry.existing)
    if dry_run:
        for line in parsed.header:
            print(f"header, not carried over  {line[:90]}")
        for entry in plan:
            mode = "present" if entry.existing else ("done   " if entry.item.done else "open   ")
            print(f"{mode}  {entry.item.created:19}  {entry.path}")
            print(f"           {entry.item.text[:90]}")
        print(f"{len(plan)} memos would move out of {OLD}, {reused} already there; "
              f"{len(parsed.header)} header line(s) not carried over")
        return 0
    try:
        for entry in plan:
            if not entry.existing:
                write_one(root, entry)
    except OSError as exc:
        print(f"could not write {getattr(exc, 'filename', '?')} ({exc}) — {OLD} left in place, and "
              f"a re-run picks up the memos already written")
        return 3
    results = check_each(parsed.items, written_memos(root))
    for _, line in results:
        print(line)
    if any(not ok for ok, _ in results):
        print(f"{OLD} left in place — nothing was removed, and a re-run picks up where this stopped")
        return 3
    # Only now, with every item asserted present exactly once, does the source go.
    try:
        os.remove(old_path)
    except OSError as exc:
        print(f"every item is in place but {OLD} could not be removed ({exc}) — remove it by hand")
        return 3
    for line in parsed.header:
        print(f"header, not carried over  {line[:90]}")
    print(summarise(parsed.items, reused))
    return 0


def apply_already_done(root: str) -> int:
    """A second `apply`, where the first already removed the source.

    Exits 0 or 3 and never crashes: the first draft opened the file it had just deleted
    and died with FileNotFoundError, which the interpreter reports as exit 1 — the code
    that means "does not apply" everywhere else in this system, and so the one reading
    that would have recorded the repo as never needing the step at all.
    """
    written = written_memos(root)
    if not written:
        print(f"{OLD} is not on disk and .claude/memos/ holds nothing — there is no backlog here to "
              f"move, which is a question for a human rather than an apply")
        return 3
    head = head_backlog(root)
    if head.state == "unknown":
        print(f"{len(written)} memo file(s) under .claude/memos/ and no {OLD}, but git could not be "
              f"asked what HEAD carries ({head.detail}), so the per-item assertion could not be made")
        return 3
    if head.state == "absent":
        print(f"already migrated: {len(written)} memo file(s) under .claude/memos/ and no {OLD}; "
              f"nothing to read back from HEAD ({head.detail}), so the shape is the whole assertion")
        return 0
    return assert_against_head(head.text, written, "already migrated")


def cmd_verify(root: str) -> int:
    """Is this repo in the shape the convention requires — never, did a migration run here.

    Asking the second question inverts the answer on exactly the repos that did the work:
    committing the migration takes `memos.md` out of HEAD, so a verify keyed on reading it
    back reports NOT COVERED, `/adopt` falls through to probe, and four repos already in
    the target shape get recorded as never having applied (CD1).
    """
    if os.path.isfile(os.path.join(root, OLD)):
        print(f"{OLD} is still on disk — the backlog has not moved into .claude/memos/")
        return 3
    if not os.path.isdir(os.path.join(root, ".claude", "memos")):
        print(f"no .claude/memos/ to read, and no {OLD} either — whether this repo wants a backlog is "
              f"not a shape this script can observe")
        return 2
    written = written_memos(root)
    if not written:
        print(".claude/memos/ holds no .md file — an empty backlog directory is not the target shape, "
              "and passing on one would make this check unable to tell done from never-run")
        return 3
    print(f"{len(written)} memo file(s) under .claude/memos/, and no {OLD}")
    head = head_backlog(root)
    if head.state == "unknown":
        # Not exit 2: the shape above IS observable, and exit 2 sends /adopt on to probe, which
        # answers "already a directory" and files the repo `n/a — does not apply` — the inversion
        # CD1 exists to stop. A stronger assertion that could not be run is an assertion failure.
        print(f"git could not be asked what HEAD carries ({head.detail}), so the per-item assertion "
              f"this step owes an uncommitted migration could not be made — fix that and re-run "
              f"rather than recording a pass nobody made")
        return 3
    if head.state == "absent":
        print(f"nothing to read back from HEAD — {head.detail} — so the shape above is the whole "
              f"assertion; committing the migration is what takes the pre-migration file out of HEAD")
        return 0
    return assert_against_head(head.text, written, "asserted")


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
