#!/usr/bin/env python3
"""Refuse to create a Windows link from a shell that cannot create one the OS will follow.

Windows does not follow a reparse point created by a non-administrator — RedirectionGuard,
`ERROR_UNTRUSTED_MOUNT_POINT`, WinError 448 — and it refuses a symlink exactly as readily as a
junction. A link made from an ordinary Git Bash is therefore created, resolves from the shell that
made it, and raises somewhere else entirely. Measured 2026-09-18 on the Windows machine: three
links under `~/.claude` and all 19 project memory caches were in that state, and the one that
surfaced dropped a whole machine out of `/github-status` while leaving `/adopt` unable to load its
own engine. Nothing reported any of it, because every process that had looked was one of the ones
that could still follow them.

So this blocks the creation instead of letting it half-succeed, and hands back the command to run
from an elevated PowerShell. The measurements and the repair are in
`learnings/git-bash-windows-symlinks.md`.

What it cannot tell apart is running these commands from writing about them: a heredoc containing
this very paragraph matches as readily as a real invocation. That is the standing limit of a
content gate — see the 2026-08-19 finding in the hooks SKILL — and it is why a block quotes the
command it saw rather than only asserting one existed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# The `if` gate in settings.json fails open on any command the harness cannot decompose, so the
# command text is re-read here rather than trusted. Command position rather than anywhere in the
# string: `grep -rn "New-Item -ItemType Junction" .` names the words without running them.
INVOKER_RE = re.compile(r"(?:^|[;&|(`]\s*|\$\(\s*)(?:powershell|pwsh|cmd|mklink)\b", re.I)
LINK_RE = re.compile(r"-ItemType\s+(?:Junction|SymbolicLink)\b|\bmklink\b", re.I)

# `IsInRole(Administrator)` answers "is this shell elevated", which is the question that decides
# here — deliberately not the group-membership form that `learnings/windows-openssh-over-tailscale.md`
# calls for, since that one answers "may this account elevate" and a link made from an unelevated
# admin shell is untrusted just the same.
# The outer parentheses are what make the cast apply: without them PowerShell binds `.IsInRole` to
# `WindowsIdentity::GetCurrent()`, which has no such method, and the probe fails with an error
# rather than an answer — measured, and it presented as "elevation could not be determined".
ELEVATION = ("([Security.Principal.WindowsPrincipal]"
             "[Security.Principal.WindowsIdentity]::GetCurrent())"
             ".IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)")


def creates_a_link(command: str) -> bool:
    """Whether `command` runs a Windows link-creating verb, rather than merely containing one."""
    return bool(INVOKER_RE.search(command) and LINK_RE.search(command))


def elevated() -> bool | None:
    """Whether this shell can create a link Windows will follow, or None when PowerShell won't say.

    None is not False: an unanswerable probe and a plain "no" call for different sentences, and
    reporting the first as the second would name a cause nobody has evidence for.
    """
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", ELEVATION],
                              capture_output=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    answer = (done.stdout or "").strip().casefold()
    if done.returncode != 0 or answer not in ("true", "false"):
        return None
    return answer == "true"


def main() -> int:
    # Cheapest first: this whole guard is about one platform, and the `if` gate can fire anywhere.
    if os.name != "nt":
        return 0
    # An unrecognised argv[1] is a no-op, so a stale command string in settings.json cannot
    # resurrect a mode that was removed.
    if len(sys.argv) > 1:
        return 0
    try:
        payload = json.load(sys.stdin)
    except BaseException:
        payload = {}
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not creates_a_link(command):
        return 0

    can = elevated()
    if can:
        return 0
    why = ("this shell is not elevated" if can is False else
           "whether this shell is elevated could not be determined")
    # ASCII only: this lands on a Windows console whose codepage is not UTF-8, and a mangled
    # explanation of a mangled link is not the place to find out.
    print(f"Blocked: {why}, and a Windows link created without elevation is one the OS can refuse "
          f"to follow (WinError 448) from any other process, including the one that has to read it.\n"
          f"The command: {command.strip()[:300]}\n"
          f"Create it from an elevated PowerShell instead, or hand that command to the user. "
          f"See ~/.claude/learnings/git-bash-windows-symlinks.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Never disrupt Claude Code, whatever went wrong here. A guard that cannot run is not a
        # reason to refuse the tool call it was inspecting.
        raise SystemExit(0)
