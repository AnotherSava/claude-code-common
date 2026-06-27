#!/usr/bin/env python3
"""Deterministic backlog helper for the /memo skill.

Keeps the timestamp and the rendered listing from drifting, and aligns wrapped
text correctly around multibyte characters (the bash `fold` approach mis-counted
the em-dash). Same idea as the github-status skill: a script renders the aligned
view; the caller pastes it verbatim.

  memos.py add "<text>"   append an open memo (one line), stamped local-time 24h
  memos.py list           numbered, newest-first, wrapped + aligned listing
  memos.py count          "<open> open · <done> done"

The file is <repo root>/.claude/memos.md (git toplevel, else the current dir).
"""
import datetime
import os
import re
import shutil
import subprocess
import sys
import textwrap

# Emit UTF-8 regardless of the platform console codepage, so the em-dash survives (Windows defaults
# stdout to cp1252, which would mangle it).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


FILE = os.path.join(_root(), ".claude", "memos.md")
HEADER = (
    "# Memos\n\n"
    "Off-task ideas captured during sessions, to revisit later. "
    "Managed by `/memo`; open items resurface at session start, task completion, and commit.\n"
)
OPEN_RE = re.compile(r"^- \[ \] (\d{4}-\d\d-\d\d \d\d:\d\d) — (.*)$")
DONE_RE = re.compile(r"^- \[x\] ", re.I)


def _text():
    try:
        return open(FILE, encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def cmd_add(args):
    text = " ".join(" ".join(args).split())  # collapse to a single clean line
    if not text:
        sys.exit("memo text required")
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    if not os.path.exists(FILE):
        open(FILE, "w", encoding="utf-8").write(HEADER + "\n")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")  # local timezone, 24-hour
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(f"- [ ] {ts} — {text}\n")
    cmd_count(args)


def _width(args):
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


def cmd_list(args):
    width = _width(args)
    items = [m.groups() for m in (OPEN_RE.match(ln) for ln in _text().splitlines()) if m]
    if not items:
        print("(no open memos)")
        return
    items = list(reversed(items))  # newest first
    numw = len(str(len(items)))
    for i, (ts, idea) in enumerate(items, 1):
        prefix = f"{str(i).rjust(numw)}. {ts} — "
        # subsequent_indent matches the prefix's character width, so continuation lines
        # line up under the idea text on the first line (textwrap counts the em-dash as 1).
        print(textwrap.fill(idea, width=width, initial_indent=prefix, subsequent_indent=" " * len(prefix)))


def cmd_count(args):
    lines = _text().splitlines()
    o = sum(1 for ln in lines if OPEN_RE.match(ln))
    d = sum(1 for ln in lines if DONE_RE.match(ln))
    print(f"{o} open · {d} done")


def main():
    cmd, *rest = (sys.argv[1:] or ["list"])
    handler = {"add": cmd_add, "list": cmd_list, "count": cmd_count}.get(cmd)
    if not handler:
        sys.exit("usage: memos.py {add <text>|list|count}")
    handler(rest)


if __name__ == "__main__":
    main()
