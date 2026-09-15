#!/usr/bin/env python3
"""v14 — every addressed memo carries the date it was closed at the front of its name.

`.claude/memos/done/` is append-only and no command lists it: `list` and `show` in the memo
skill both resolve against the open backlog, and the command that used to delete done memos
is gone. That leaves a file browser, `ls` and `git status` as the only readers of that
directory, and a name is the only thing any of them sorts by — so the close date goes into
the name. Repos adopted before this hold done memos named by slug alone, which sort
alphabetically and say nothing about when anything was decided.

    memos-done-dated.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    memos-done-dated.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, nothing renamed
    memos-done-dated.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The close date is read from git — the commit that added the file at its `done/` path — and
never from the filesystem. An mtime is rewritten by a clone, a checkout and a rebase, so it
answers when this machine last wrote the file rather than when the memo was closed, and a
step that may not guess may not use it. A done memo git has never seen has no readable
close date at all; `probe` asks for those rather than stamping them with today.

This step deliberately does NOT declare `affects: memo`. That field makes `memos.py` refuse
outright in a repo below this version, and it is right to for v1, where reading the old
shape gives a wrong answer — an empty backlog beside a file holding thirty-three items. Here
every command keeps answering correctly on an undated `done/`: `list` and `add` never look
there, `reopen` re-derives its name from the title either way, and a close writes the new
shape beside the old one. The cost of declaring it would be blocking daily memo use in every
repo until each is walked, to buy consistency in a directory nothing yet reads wrong.
"""

import datetime
import os
import re
import subprocess
import sys

# sys.path[0] is already this directory when the engine runs the script by path; the insert is
# for a caller that reaches it another way.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MEMOS_REL = ".claude/memos"
DONE_REL = f"{MEMOS_REL}/done"
DATE_FMT = "%Y-%m-%d"
# A leading run that LOOKS like a date. Whether it is one is `strptime`'s answer, not this
# pattern's: `2026-13-45-foo.md` matches here and is not a date, and a step that accepted the
# match would record a repo as dated on a name no reader can order.
PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def _done_dir(root: str) -> str:
    return os.path.join(root, *DONE_REL.split("/"))


def _entries(root: str) -> list[str]:
    """Every memo file in done/, sorted. Non-`.md` names are left alone, as `memos.py` leaves them.

    The extension test folds case for the reason the memo helper's does: NTFS and APFS resolve
    `Case-Test.MD` and `case-test.md` to one file, so a case-sensitive test hides a file from
    this step while the filesystem still hands it to `os.replace`.
    """
    try:
        names = os.listdir(_done_dir(root))
    except OSError:
        return []
    return sorted(n for n in names
                  if n.lower().endswith(".md") and os.path.isfile(os.path.join(_done_dir(root), n)))


def _dated(name: str) -> tuple[bool, str]:
    """(is it dated, the malformed prefix that stopped this step) for one done filename."""
    match = PREFIX_RE.match(name)
    if not match:
        return False, ""
    try:
        datetime.datetime.strptime(match.group(1), DATE_FMT)
    except ValueError:
        return False, match.group(1)
    return True, ""


def _close_date(root: str, name: str) -> str:
    """The date the commit that put this file in done/ was authored, or "" when git has none.

    `--diff-filter=A` at that exact path, newest first: a memo closed, reopened and closed
    again was added there more than once, and the close that matters is the one whose result
    is on disk now. No rename detection is asked for — the move into done/ IS the addition
    this reads, and `-M` would resolve it back to the open path and answer with the capture.
    """
    rel = f"{DONE_REL}/{name}"
    try:
        out = subprocess.run(["git", "-C", root, "log", "--diff-filter=A", "--format=%ad",
                              "--date=format:" + DATE_FMT, "--", rel],
                             capture_output=True, text=True)
    except OSError:
        return ""
    if out.returncode != 0:
        return ""
    lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    return lines[0] if lines else ""


def _survey(root: str) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """(already dated, malformed, undated-with-their-close-date-or-"") over done/."""
    dated, malformed, undated = [], [], []
    for name in _entries(root):
        is_dated, bad = _dated(name)
        if is_dated:
            dated.append(name)
        elif bad:
            malformed.append(f"{name} (leading {bad} is not a date)")
        else:
            undated.append((name, _close_date(root, name)))
    return dated, malformed, undated


def _backlog_note(root: str) -> str:
    """What was read, so an exit-1 line is evidence rather than an absence."""
    memos_dir = os.path.join(root, *MEMOS_REL.split("/"))
    if not os.path.isdir(memos_dir):
        return f"there is no {MEMOS_REL}/ here, so this repo keeps no memo backlog to date"
    try:
        open_count = sum(1 for n in os.listdir(memos_dir)
                         if n.lower().endswith(".md") and os.path.isfile(os.path.join(memos_dir, n)))
    except OSError:
        open_count = 0
    return (f"{MEMOS_REL}/ holds {open_count} open memo(s) and {DONE_REL}/ holds no addressed "
            f"ones, so there is no name here to carry a close date")


def cmd_probe(root: str) -> int:
    dated, malformed, undated = _survey(root)
    if malformed:
        print(f"{len(malformed)} file(s) in {DONE_REL}/ open with something shaped like a date that is "
              f"not one, and this step will not decide which they are:")
        for item in malformed:
            print(f"  {item}")
        print("Rename them by hand to a real close date or to a bare slug, then re-run.")
        return 2
    if not dated and not undated:
        print(_backlog_note(root))
        return 1
    if not undated:
        print(f"already dated: all {len(dated)} memo(s) in {DONE_REL}/ carry the date they were closed")
        return 1
    undatable = [name for name, date in undated if not date]
    if undatable:
        print(f"{len(undatable)} of {len(undated)} undated memo(s) in {DONE_REL}/ are not in git, so the "
              f"date they were closed cannot be read:")
        for name in undatable:
            print(f"  {name}")
        print("Commit the close first and re-run — a close this step cannot date is one it would have "
              "to stamp with today, which is a guess about work done on some other day.")
        return 2
    print(f"{len(undated)} of {len(dated) + len(undated)} memo(s) in {DONE_REL}/ are named by slug alone, "
          f"so the directory sorts alphabetically rather than by when anything was decided:")
    for name, date in undated:
        print(f"  {name} -> {date}-{name}")
    return 0


def _target(name: str, date: str, taken: set[str]) -> str:
    """The dated name for `name`, unique against `taken` (folded, as the filesystem folds).

    The disambiguating suffix goes behind the slug and never inside the prefix: a `-2` wedged
    into the date would sort that memo away from the day it was closed on, which is the one
    thing the prefix exists to get right.
    """
    stem, ext = os.path.splitext(name)
    folded = {t.casefold() for t in taken}
    candidate, n = f"{date}-{stem}{ext}", 2
    while candidate.casefold() in folded:
        candidate, n = f"{date}-{stem}-{n}{ext}", n + 1
    return candidate


def cmd_apply(root: str, dry_run: bool) -> int:
    dated, malformed, undated = _survey(root)
    if malformed:
        print(f"stopped without renaming anything — {len(malformed)} file(s) in {DONE_REL}/ open with "
              f"something shaped like a date that is not one, and a step that guessed which they are "
              f"would file real work under a day it was not done on:")
        for item in malformed:
            print(f"  {item}")
        return 3
    undatable = [name for name, date in undated if not date]
    if undatable:
        print(f"stopped without renaming anything — {len(undatable)} undated memo(s) are not in git, so "
              f"their close date cannot be read:")
        for name in undatable:
            print(f"  {name}")
        return 3
    if not undated:
        if not dated:
            print(_backlog_note(root))
            return 3
        print(f"already dated: all {len(dated)} memo(s) in {DONE_REL}/ carry their close date; nothing "
              f"was renamed")
        return 0
    taken = set(_entries(root))
    plan: list[tuple[str, str]] = []
    for name, date in undated:
        target = _target(name, date, taken)
        taken.add(target)
        plan.append((name, target))
    if dry_run:
        for name, target in plan:
            print(f"would rename  {name}  ->  {target}")
        print(f"{len(plan)} memo(s) in {DONE_REL}/ would gain the date they were closed")
        return 0
    done_dir = _done_dir(root)
    for name, target in plan:
        source, destination = os.path.join(done_dir, name), os.path.join(done_dir, target)
        try:
            with open(source, "rb") as fh:
                before = fh.read()
            os.replace(source, destination)
            with open(destination, "rb") as fh:
                after = fh.read()
        except OSError as exc:
            print(f"FAILED   {name}: {exc} — every memo this step had not reached is untouched")
            return 3
        # Per item and inside apply, while the evidence still exists: the rename is the whole
        # migration, so the assertion that it moved these bytes and not a truncation of them has
        # nowhere later to live. A count would pass the moment one file vanished and another
        # doubled.
        if after != before:
            print(f"FAILED   {name}: {target} does not hold the bytes that were read from it")
            return 3
        if os.path.exists(source):
            print(f"FAILED   {name}: the undated name is still there beside {target}")
            return 3
        print(f"ok       {name}  ->  {target}")
    print(f"{len(plan)} memo(s) in {DONE_REL}/ now open with the date they were closed, read from the "
          f"commit that put each in done/; each asserted byte-identical at its new name and gone from "
          f"its old one")
    return 0


def cmd_verify(root: str) -> int:
    dated, malformed, undated = _survey(root)
    if not dated and not undated and not malformed:
        # Not a pass. "Every done memo is dated" is true of a repo that has closed none, and an
        # applied line there would claim a migration in a directory this never read.
        print(_backlog_note(root))
        return 2
    for item in malformed:
        print(f"FAIL  {item}")
    for name, _ in undated:
        print(f"FAIL  {name} is named by slug alone")
    for name in dated:
        print(f"ok    {name}")
    if malformed or undated:
        return 3
    print(f"all {len(dated)} memo(s) in {DONE_REL}/ open with a real date, so the directory reads in the "
          f"order the work was decided in")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
