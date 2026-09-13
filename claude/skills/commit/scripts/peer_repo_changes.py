#!/usr/bin/env python3
"""Report repositories OTHER than this one that this session edited and left dirty.

The commit skill's scope guard says each project's commits are handled separately, so work
that spilled into a second repo is never in the change set being committed here. This finds
those repos mechanically instead of relying on the session to remember them, and narrows the
answer to what is still uncommitted — a file a peer session already committed needs no notice.

Detection is by transcript, not by scanning for dirty repos: "this repo has uncommitted
changes" is true of half the tree at any moment and says nothing about the current session.
Only a path this session actually wrote makes a peer repo its business.

Limit worth knowing: a file written by a shell command (`sed -i`, a generator, a build) is
invisible here, because only Edit/Write/NotebookEdit record their target as a tool argument.
The report says so rather than implying the list is exhaustive.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

WRITE_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
PATH_KEYS = ("file_path", "notebook_path")


def _resolve_transcript() -> tuple[str | None, str]:
    """Locate this session's transcript, reporting how it was found."""
    projects = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session_id:
        matches = glob.glob(os.path.join(projects, "*", f"{session_id}.jsonl"))
        if matches:
            return max(matches, key=os.path.getmtime), "session-id"
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", os.getcwd())
    candidates = glob.glob(os.path.join(projects, mangled, "*.jsonl"))
    if not candidates:
        return None, "UNRESOLVED"
    return max(candidates, key=os.path.getmtime), "newest-in-cwd-dir"


def _written_paths(transcript: str) -> list[str]:
    """Every file path this session passed to a file-writing tool, in first-seen order."""
    seen: dict[str, None] = {}
    with open(transcript, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                if block.get("name") not in WRITE_TOOLS:
                    continue
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                for key in PATH_KEYS:
                    value = tool_input.get(key)
                    if isinstance(value, str) and value.strip():
                        seen.setdefault(os.path.realpath(value), None)
    return list(seen)


def _git(root: str, *args: str) -> str | None:
    """Run a git command in `root`, returning raw stdout or None when it fails.

    Deliberately unstripped: porcelain encodes the index/worktree state in the first two
    columns, so ` M file` starts with a meaningful space. Stripping it here shifted every
    such path one character left and quietly dropped the repo from the report.
    """
    try:
        done = subprocess.run(("git", "-C", root, *args), capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _toplevel(path: str) -> str | None:
    """The git repository containing `path`, or None when it is not in one."""
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    while directory and not os.path.isdir(directory):
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent
    if not directory:
        return None
    top = _git(directory, "rev-parse", "--show-toplevel")
    return os.path.realpath(top.strip()) if top and top.strip() else None


def _rebase(path: str, root: str) -> str:
    """Re-spell `path` under git's own spelling of `root`.

    `~/.claude/learnings` is a symlink whose stored target says `projects` while git reports
    `Projects`, and a case-insensitive filesystem keeps both working. So a global learning
    written through the symlink realpaths to a string that never equals the one built from
    `git rev-parse`, and comparing the two directly drops the file with no error — which is
    exactly the case this check exists for.
    """
    for base in (root, os.path.realpath(root)):
        prefix = base.rstrip(os.sep) + os.sep
        if path.casefold().startswith(prefix.casefold()):
            return os.path.join(root, path[len(prefix):])
    return path


def _dirty_paths(root: str) -> set[str] | None:
    """Absolute paths of every modified or untracked file in `root`.

    `-z` because this output is parsed rather than shown: without it `core.quotepath`
    escapes non-ASCII bytes to octal and wraps the path in quotes, so a peer repo holding
    a Cyrillic or accented filename yields a string that matches nothing and the file goes
    silently unreported.
    """
    porcelain = _git(root, "status", "--porcelain", "-z")
    if porcelain is None:
        return None
    dirty: set[str] = set()
    fields = porcelain.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        # Two status columns, one separator, then the path — never lstrip this.
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        # Under -z a rename or copy carries its ORIGINAL path in the next field; the entry
        # itself already holds the new name, which is the one actually on disk.
        if "R" in status or "C" in status:
            index += 1
        dirty.add(os.path.normpath(os.path.join(root, path)))
    return dirty


def main() -> int:
    here = _toplevel(os.getcwd())
    transcript, how = _resolve_transcript()
    if transcript is None:
        print("peer-repos: UNRESOLVED — no transcript found, so peer edits could not be checked")
        return 0

    by_repo: dict[str, list[str]] = {}
    for path in _written_paths(transcript):
        root = _toplevel(path)
        if root is None or root == here:
            continue
        by_repo.setdefault(root, []).append(_rebase(path, root))

    if not by_repo:
        print("peer-repos: none — this session wrote no files outside this repository")
        print(f"(transcript resolved via {how}; shell-written files are not visible to this check)")
        return 0

    reported = 0
    for root in sorted(by_repo):
        dirty = _dirty_paths(root)
        if dirty is None:
            print(f"peer-repos: {root} — UNREADABLE (git status failed); check it by hand")
            reported += 1
            continue
        outstanding = [p for p in by_repo[root] if p in dirty]
        if not outstanding:
            continue
        reported += 1
        print(f"peer-repos: {os.path.basename(root)}  ({root})")
        print(f"  agent name to match in ListAgents: {os.path.basename(root)}")
        for path in sorted(outstanding):
            print(f"  uncommitted: {os.path.relpath(path, root)}")
        others = len(dirty) - len(outstanding)
        if others:
            print(f"  ({others} more file(s) dirty there that this session did not touch — not yours to mention)")

    if not reported:
        print("peer-repos: none — every file this session wrote elsewhere is already committed there")
    print(f"(transcript resolved via {how}; shell-written files are not visible to this check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
