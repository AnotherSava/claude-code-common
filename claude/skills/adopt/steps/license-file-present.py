#!/usr/bin/env python3
"""v10 — assert a LICENSE sits at the repo root, and leave the writing to a human.

A repo carrying no LICENSE grants nothing to anyone holding a copy, which is the same
position as all rights reserved arrived at by accident. The convention writes the
position down instead: a file at the repo root, MIT for a public repo and all rights
reserved for a private one, with three repos on GPL-3 deliberately.

This step **detects and never fixes**, and its `apply` is the finding rather than the
change. Three reasons, each sufficient on its own:

**The choice is legally the user's.** A LICENSE this script picked is a grant nobody
made, offered to everyone holding a copy from the commit that introduced it — and
deleting the file later does not reach the copies or the older commits.

**The default flips on visibility, which is a network fact.** `gh repo view --json
isPrivate` is what answers it, and a step script may not make that call. So visibility
is a question this step prints, never one it resolves.

**Three repos deviate from the default on purpose.** Writing MIT over a considered
GPL-3 decision would be guessing where guessing costs the most, and `apply` may never
guess.

So `probe` returns 2 in every repo, `/adopt` never reaches `apply`, and `verify` is
what carries the fleet: it hands a free `applied` line to the twelve repos already
holding a license instead of asking all fifteen a question most of them answered years
ago. That is the trade a script buys over a judgement-only step here.

Presence is the whole assertion. Which license it is, and whether it matches the repo's
visibility, is the human half and lives under `## By hand, after the script`, so a
recorded note never claims more than was looked at.

    license-file-present.py probe  <repo-root>              2 always, with the question
    license-file-present.py apply  <repo-root> [--dry-run]  3 always, and nothing is written
    license-file-present.py verify <repo-root>              0 in shape · 2 unobservable · 3 not
"""

import datetime
import json
import os
import subprocess
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert
# is what lets the authoring gate import this module directly as well.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

# Both candidate texts print verbatim, and an em-dash through Windows' cp1252 console default
# raises rather than prints — which would turn a finding into an exit 3 for the wrong reason.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The names that count as a license at the repo root. Matched as a case-folded stem beside a
# case-folded extension, rather than against a literal list, so `license`, `License.md` and
# `COPYING` all read the same here as they do on a case-sensitive filesystem.
STEMS = ("license", "copying")
SUFFIXES = ("", ".md", ".txt")
ACCEPTED = "LICENSE, LICENSE.md, LICENSE.txt or COPYING"
VISIBILITY_CMD = "gh repo view --json isPrivate -q .isPrivate"

# The same two texts the `github-create` skill seeds a new repo with, and the same `[year]` /
# `[fullname]` slots, which are GitHub's own template spelling. Held here as text because the
# alternative is `gh api licenses/mit`, and a step script may not touch the network.
MIT = """MIT License

Copyright (c) [year] [fullname]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

RESERVED = """Copyright (c) [year] [fullname]

All rights reserved.

No permission is granted to use, copy, modify, merge, publish, distribute,
sublicense, or sell this software or any part of it. If you have been given
access to this repository, that access does not by itself grant any of those
rights; any permission must be given separately and in writing."""


class Candidate(NamedTuple):
    """One repo-root entry whose name reads as a license, and what was actually found there."""

    name: str
    state: str  # "text" · "empty" · "directory" · "unreadable" — an explicit field, not an empty body
    body: str
    detail: str


def listdir(path: str) -> list[str]:
    """Sorted entries, or nothing when the directory cannot be read — no caller here may die on that."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def candidates(root: str) -> tuple[list[Candidate], str]:
    """Every repo-root entry whose name reads as a license, classified.

    The four states are kept apart rather than collapsed into present/absent, because they
    lead to different exits: text is the target shape, empty and directory are the wrong
    shape observed, and unreadable is the one case where the shape was not observed at all.
    """
    try:
        names = sorted(os.listdir(root))
    except OSError as exc:
        return [], f"the repo root could not be listed ({exc.strerror or exc})"
    found: list[Candidate] = []
    for name in names:
        stem, extension = os.path.splitext(name)
        if stem.casefold() not in STEMS or extension.casefold() not in SUFFIXES:
            continue
        path = os.path.join(root, name)
        if os.path.isdir(path):
            found.append(Candidate(name, "directory", "", "it is a directory rather than a file"))
            continue
        try:
            # errors="replace" so a license stored in some other encoding is still readable enough
            # to be called non-empty; this step never parses the text, so a mangled byte costs nothing.
            with open(path, encoding="utf-8", errors="replace") as handle:
                body = handle.read()
        except OSError as exc:
            found.append(Candidate(name, "unreadable", "", f"it could not be read ({exc.strerror or exc})"))
            continue
        found.append(Candidate(name, "text" if body.strip() else "empty", body, "" if body.strip() else "it holds nothing"))
    return found, ""


def first_line(body: str) -> str:
    """The first line with anything on it — evidence of presence, never an identification.

    A GPL text opens on a centred title and MIT on a bare one, so this reads as a label. It is
    not parsed and nothing branches on it: which license a repo carries is the half this step
    leaves to a human, and a check keyed on this string would fail the three deliberate GPL-3
    repos for being what they chose to be.
    """
    for line in body.splitlines():
        if line.strip():
            return line.strip()[:70]
    return ""


def describe(found: list[Candidate]) -> str:
    """One line saying what is at the repo root, for the head of a question or a refusal."""
    if not found:
        return f"there is no {ACCEPTED} at the repo root, so this repo's license position is written down nowhere"
    text = [item for item in found if item.state == "text"]
    if text:
        return (f"{', '.join(item.name for item in text)} is already at the repo root "
                f"(first line: {first_line(text[0].body)})")
    return "; ".join(f"{item.name} is at the repo root but {item.detail}" for item in found)


def holder(root: str) -> tuple[str, str]:
    """Who the candidate texts name, read from this repo's own git config.

    The conventions say the current year and the user's name from git config, so this is the
    documented source rather than a guess — and it is a local read, not a network one. Where
    git will not answer, the slot stays a placeholder that cannot be mistaken for a real name
    and the reason is printed beside the text.
    """
    try:
        done = subprocess.run(["git", "-C", root, "config", "user.name"], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError):
        return "{{full-name}}", "git could not be run here, so the holder is left as a placeholder to fill in"
    name = done.stdout.strip() if done.returncode == 0 else ""
    if not name:
        return "{{full-name}}", "git config user.name is not set here, so the holder is left as a placeholder to fill in"
    return name, "holder read from this repo's git config user.name, year from today's date"


def fill(template: str, year: str, name: str) -> str:
    """Substitute both slots. A template missing one would print a license naming nobody."""
    for slot in ("[year]", "[fullname]"):
        if slot not in template:
            return f"this candidate text has no {slot} slot, so it is printed unfilled:\n{template}"
    return template.replace("[year]", year).replace("[fullname]", name)


def manifests(root: str) -> list[str]:
    """What each nearby `package.json` currently declares as its license.

    The root and one level below it, which is where this fleet keeps them — several projects
    hold theirs under `web/`. Reported and never asserted: a manifest contradicting the LICENSE
    is what dependency scanners read, and it is the half of the change most easily forgotten,
    but which value is right depends on the license the user has not chosen yet.
    """
    # walk-unfiltered: and unlike the other waivers in this directory, this one marks a known defect
    # rather than a case the filter does not apply to. A gitignored manifest one level down — a
    # scratch clone, a build tree — is reported here as though it were this project's, so the advice
    # about dependency scanners names a file no clone receives. It is report-only: `cmd_verify` never
    # reads this list and `cmd_apply` writes nothing, so no recorded line depends on it, which is why
    # it is waived and memo'd rather than fixed inside a change set about something else.
    places = ["."] + [name for name in listdir(root)
                      if not name.startswith(".") and name != "node_modules"
                      and os.path.isdir(os.path.join(root, name))]
    out: list[str] = []
    for place in places:
        path = os.path.join(root, place, "package.json")
        if not os.path.isfile(path):
            continue
        shown = "package.json" if place == "." else f"{place}/package.json"
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            out.append(f"{shown} could not be read ({exc})")
            continue
        declared = data.get("license") if isinstance(data, dict) else None
        out.append(f"{shown} declares \"license\": {declared!r}" if declared else f"{shown} declares no license field")
    return out


def print_question(found: list[Candidate]) -> None:
    """The question `/adopt` puts to the user, with this repo's own state in front of it."""
    print(describe(found))
    if any(item.state == "text" for item in found):
        print("verify answers this repo without a question, and what is left is whether that license is the "
              "one its visibility calls for — the human half, which no exit code here covers.")
        return
    print(f"Is this repo public or private? `{VISIBILITY_CMD}` answers it, and the conventions default a "
          f"public repo to MIT and a private one to all rights reserved.")
    print("Three repos here carry GPL-3 on purpose, so the default is a starting point rather than an answer.")
    print("Run `apply` for this step to see both candidate texts in full, with the year and holder filled in. "
          "Write the chosen one to LICENSE at the repo root and re-run, which records applied.")
    print("Record n/a if this is not a project whose terms matter, and declined if the absence is deliberate "
          "and the implicit all-rights-reserved default is the position wanted.")


def cmd_probe(root: str) -> int:
    """Always 2: this step has no case in which a script may act, and none in which it may skip.

    Exit 1 would need positive evidence that a repo wants no license decision, and no file on
    disk carries that — an absent LICENSE is the finding itself, not proof there is nothing to
    find (CD4). Exit 0 would send `/adopt` on to an apply that exists only to refuse. So the
    answer is the question, and a human gives the n/a or the declined.
    """
    found, failure = candidates(root)
    if failure:
        print(f"{failure}, so whether a license is here could not be read at all.")
        return 2
    print_question(found)
    return 2


def cmd_apply(root: str, dry_run: bool) -> int:
    """Always 3: the finding and the two candidate texts, and not one byte written.

    `/adopt` never reaches this, since probe cannot return 0. It is here for the human who has
    the question in front of them and wants the text to paste, which is why it prints both
    candidates rather than naming them.
    """
    found, failure = candidates(root)
    print("This step never writes a LICENSE. Which license a repo carries is a legal choice, the default "
          "flips on a visibility only the network can answer, and three repos here deviate from that default "
          "on purpose — so the file is written by hand and this stops with the finding.")
    if dry_run:
        print("--dry-run changes nothing about that: no file is written either way.")
    print(f"  {failure}" if failure else f"  {describe(found)}")
    if any(item.state == "text" for item in found):
        print("  Nothing to add. Re-run verify, which records this repo as already in the target shape.")
        return 3
    year, (name, source) = str(datetime.datetime.now().year), holder(root)
    print(f"\nWhich one this repo wants follows from its visibility — `{VISIBILITY_CMD}` answers that, and it "
          f"is a network call no step script may make. Public defaults to MIT, private to all rights reserved.")
    print(f"Both texts below are filled in and ready to copy ({source}).")
    for label, template in (("public — MIT", MIT), ("private — all rights reserved", RESERVED)):
        print("\n" + f"--- LICENSE for a repo that is {label} ".ljust(70, "-"))
        print(fill(template, year, name))
    print("-" * 70)
    nearby = manifests(root)
    for line in nearby:
        print(f"also: {line}")
    if nearby:
        print("A manifest naming a different license contradicts the file and is what dependency scanners read; "
              "npm's spelling for no grant is \"license\": \"UNLICENSED\" beside \"private\": true.")
    print("\nWrite the chosen text to LICENSE at the repo root, then re-run verify for this step.")
    return 3


def cmd_verify(root: str) -> int:
    """Is a license present at the repo root — never which one, and never who put it there.

    Content is deliberately unchecked: three repos hold GPL-3 against a default of MIT, so a
    check that read the text would report the fleet's most considered decisions as failures.
    Presence is what the note then claims, and no more.
    """
    found, failure = candidates(root)
    if failure:
        print(f"{failure}, so whether a license is present is not a shape this script can observe")
        return 2
    text = [item for item in found if item.state == "text"]
    if text:
        for item in text:
            print(f"{item.name} at the repo root, {len(item.body.encode('utf-8'))} bytes, "
                  f"first line: {first_line(item.body)}")
        print("a license is present; which license it is, and whether it suits this repo's visibility, is the "
              "half this step leaves to a human")
        return 0
    if any(item.state == "unreadable" for item in found):
        for item in found:
            print(f"{item.name} at the repo root: {item.detail or 'it holds text'}")
        print("a license may well be here, but it could not be read, so whether it holds anything is not "
              "observable — fix that and re-run rather than recording a pass nobody made")
        return 2
    if found:
        for item in found:
            print(f"{item.name} at the repo root: {item.detail}")
        # An empty file passes every presence check ever written and grants exactly as much as no file at
        # all, so treating it as the shape would make this check unable to tell done from never-started.
        print("a name that reads as a license from a file listing while granting nothing is the absent case "
              "wearing a filename, not the target shape")
        return 3
    print(f"no {ACCEPTED} at the repo root — this repo grants nothing and says nowhere that it meant to")
    return 3


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
