#!/usr/bin/env python3
"""Cases for the window `claude/skills/wrap-up/scripts/session_scan.py` digests: where the section being wrapped up begins.

Each case writes a transcript under a scratch HOME and runs the script on it by session id, then reads the `window:`
header and which messages reached the conversation body, since those are what /wrap-up reviews.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCAN = os.path.join(ROOT, "claude", "skills", "wrap-up", "scripts", "session_scan.py")

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got != want:
        failures.append(f"  FAIL {label}: got {got!r}, want {want!r}")


def command(name: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": f"<command-name>/{name}</command-name>"}}


def said(who: str, text: str) -> dict:
    return {"type": who, "message": {"role": who, "content": [{"type": "text", "text": text}]}}


def invoked(skill: str) -> dict:
    """Claude starting a skill through the Skill tool, as it does when another agent's message asks for it."""
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "s", "name": "Skill", "input": {"skill": skill}}]}}


def ran(command_line: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": command_line}}]}}


COMMITTED = ran("python3 ~/.claude/skills/shared/commit.py -F msg.txt --reviewed a.py")


def scan(home: str, session: str, records: list[dict]) -> tuple[str, str]:
    """The `window:` line and the conversation body for a transcript made of these records."""
    folder = os.path.join(home, ".claude", "projects", "-scratch")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{session}.jsonl"), "w", encoding="utf-8") as handle:
        for index, record in enumerate(records):
            handle.write(json.dumps({**record, "timestamp": f"2026-11-03T10:{index:02d}:00Z"}) + "\n")
    # Python's expanduser reads USERPROFILE on Windows and HOME elsewhere, so the scratch home needs both.
    out = subprocess.run([sys.executable, SCAN, "--session-id", session], capture_output=True, text=True, env={**os.environ, "HOME": home, "USERPROFILE": home}, timeout=30).stdout
    window = next((line for line in out.splitlines() if line.startswith("window:")), "")
    return window, out.split("=== conversation ===", 1)[-1]


def main() -> int:
    with tempfile.TemporaryDirectory() as home:
        window, body = scan(home, "a", [command("clear"), said("user", "first task"), command("wrap-up"), said("assistant", "summary one"), said("user", "go"), COMMITTED, said("user", "second task")])
        check("an earlier /wrap-up bounds the window", window.startswith("window: clipped to the last /wrap-up"), True)
        check("work before it is left out, its own exchange and what follows kept", ("first task" in body, "summary one" in body, "second task" in body), (False, True, True))

        window, body = scan(home, "b", [command("clear"), said("user", "first task"), command("wrap-up"), said("assistant", "summary one"), COMMITTED, said("user", "second task"), command("wrap-up")])
        check("the run's own trailing /wrap-up is not a boundary", (window.startswith("window: clipped to the last /wrap-up"), "first task" in body, "second task" in body), (True, False, True))

        window, body = scan(home, "c", [said("user", "old work"), command("clear"), said("user", "new work")])
        check("with no earlier /wrap-up the last /clear bounds it", (window.startswith("window: clipped to the last /clear"), "old work" in body), (True, False))

        window, body = scan(home, "d", [command("wrap-up"), said("assistant", "summary"), COMMITTED, said("user", "more"), command("clear"), said("user", "after clear")])
        check("a /clear after the last /wrap-up wins", (window.startswith("window: clipped to the last /clear"), "more" in body, "after clear" in body), (True, False, True))

        window, body = scan(home, "f", [command("clear"), said("user", "first task"), command("wrap-up"), said("assistant", "summary one"), said("user", "wait, fix X first"), said("user", "second task"), command("wrap-up")])
        check("an earlier /wrap-up that never reached step 8 is not a boundary", (window, "first task" in body, "second task" in body), ("window: whole transcript", True, True))

        window, body = scan(home, "g", [command("clear"), said("user", "first task"), command("wrap-up"), said("user", "stop"), command("yolo"), COMMITTED, said("user", "second task"), command("wrap-up")])
        check("a commit made by a later command does not finish an earlier /wrap-up", (window, "first task" in body), ("window: whole transcript", True))

        window, body = scan(home, "h", [command("clear"), said("user", "first task"), command("wrap-up"), said("assistant", "summary one"), said("user", "hold"), ran("python3 ~/.claude/scripts/review_scope.py advance"), said("user", "second task")])
        check("a bookmark advance alone finishes a /wrap-up", (window.startswith("window: clipped to the last /wrap-up"), "first task" in body), (True, False))

        window, body = scan(home, "j", [command("clear"), said("user", "first task"), said("user", "please run /wrap-up and answer hold"), invoked("wrap-up"), said("assistant", "summary one"), ran("python3 ~/.claude/scripts/review_scope.py advance"), said("user", "second task")])
        check("a /wrap-up Claude invoked through the Skill tool bounds the window like a typed one", (window.startswith("window: clipped to the last /wrap-up"), "first task" in body, "CLAUDE invoked /wrap-up" in body, "second task" in body), (True, False, True, True))

        window, body = scan(home, "k", [command("clear"), said("user", "first task"), command("wrap-up"), invoked("reflect"), said("assistant", "summary one"), said("user", "go"), invoked("peer"), COMMITTED, said("user", "second task")])
        check("a /reflect or /peer the run invokes itself before step 8 leaves the commit with the /wrap-up", (window.startswith("window: clipped to the last /wrap-up"), "first task" in body, "summary one" in body), (True, False, True))

        window, body = scan(home, "i", [command("clear"), said("user", "first task"), command("wrap-up"), command("login"), command("frontend-design:frontend-design"), command("memo"), said("user", "go"), COMMITTED, said("user", "second task"), command("wrap-up")])
        check("a built-in, plugin or non-committing skill typed mid-run leaves the commit with the /wrap-up", (window.startswith("window: clipped to the last /wrap-up"), "first task" in body), (True, False))

        window, _ = scan(home, "e", [command("clear"), said("user", "only work")])
        check("a transcript that opens with /clear drops nothing", window, "window: whole transcript")

    print(f"session scan tests: {f'{len(failures)} failure(s)' if failures else 'all cases behave'}")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
