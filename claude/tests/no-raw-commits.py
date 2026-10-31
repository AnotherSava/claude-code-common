#!/usr/bin/env python3
"""No skill commits except through `claude/skills/shared/commit.py`.

`commit.py` is where every commit's checks live — the exact staged set, the message rules, the privacy scan, the
signature. A skill that runs `git commit` itself skips all of them, and nothing else would notice: the commit looks
like any other until someone reads what it holds.

Two ways a skill can commit on its own, and both are read:

  a grant      its SKILL.md `allowed-tools` line grants `git commit`, which is what lets a run commit
               without a permission prompt
  a script     a `.py` or `.sh` file under a skill runs `git commit`

`shared/commit.py` is the one script allowed to. Prose that mentions `git commit` — "never run `git commit`" — is
neither, so it is not read.

Usage:  python claude/tests/no-raw-commits.py
Exit:   0 nothing commits on its own, 1 something does
"""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SKILLS = os.path.join(REPO, "claude", "skills")
ALLOWED_SCRIPT = os.path.join(SKILLS, "shared", "commit.py")

GRANT = re.compile(r"Bash\(git commit\b[^)]*\)")
# `git commit` as a shell command, or as an argv list `["git", ..., "commit"` in Python.
SCRIPT_CALL = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b|[\"']git[\"'][^\]\n]*[\"']commit[\"']")


def allowed_tools(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---\n"):
        return ""
    front = text[4:text.find("\n---", 4)]
    match = re.search(r"^allowed-tools:(.*)$", front, re.M)
    return match.group(1) if match else ""


def main() -> int:
    failures = []
    for root, dirs, files in os.walk(SKILLS):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, REPO)
            if name == "SKILL.md":
                for grant in GRANT.findall(allowed_tools(path)):
                    failures.append(f"{rel} grants {grant}, so a run can commit without shared/commit.py's checks")
            elif name.endswith((".py", ".sh")) and os.path.realpath(path) != os.path.realpath(ALLOWED_SCRIPT):
                with open(path, encoding="utf-8", errors="replace") as handle:
                    for number, line in enumerate(handle, 1):
                        if SCRIPT_CALL.search(line) and not line.lstrip().startswith("#"):
                            failures.append(f"{rel}:{number} runs git commit itself; route it through shared/commit.py")
    if failures:
        print("no raw commits: {0} place(s) commit outside shared/commit.py\n".format(len(failures)))
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("no raw commits: every skill commits through shared/commit.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
