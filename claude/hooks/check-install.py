#!/usr/bin/env python3
"""Verify every symlink and git setting this dotfiles repo installs.

    python -S ~/.claude/hooks/check-install.py         # human report, always prints
    python -S ~/.claude/hooks/check-install.py hook     # SessionStart hook, silent when healthy

Why this exists: a missing link is silent in a way that looks like working
software. `~/.claude/output-styles` was never created on one of the two
machines, so `outputStyle` in settings.json resolved to nothing and two passes
of response-style rules had been inert there since the day they shipped, while
the other machine applied them normally. Same repo, same committed settings,
opposite behaviour, nothing to see in git. Each link fails differently and
quietly: no `memory` link sends saved memories to a directory outside the repo,
no `learnings` link makes every lookup come back empty as though nothing had
been written down, no `.gitignore` link stops excluding what it excludes.

**A missing link is a level, not an edge** — it stays broken until someone fixes
it — so sampling it once per session catches it reliably, which is not true of
the state checks warned about in feedback_sample_level_miss_edge.

What it cannot check, stated because a blank result must never read as a pass:
this script is reached *through* `~/.claude/hooks`, and it only runs because
`~/.claude/settings.json` was read. Those two links cannot be verified from
here — but nothing else runs either when they are broken, so the hook firing at
all is what vouches for them.

Paths are compared with `os.path.samefile`, never as strings. `realpath`
substitutes the symlink's stored target text, and these links store `projects`
where the disk spells it `Projects`; a string comparison therefore passes or
fails depending on whether the script was invoked through the symlink or from
the repo. Comparing st_dev/st_ino sidesteps spelling entirely, and it also
catches a link that is really a copy — the failure mode Git-Bash `ln -s`
produces on Windows, which every textual check reports as healthy.
See learnings/comparing-paths-symlinks-and-case.md.
"""

from __future__ import annotations

import os
import subprocess
import sys

# (link path, path within the repo). Mirrors the install blocks in README.md; a
# link added there needs a line here or it goes unchecked.
LINKS: list[tuple[str, str]] = [
    ("~/.claude/CLAUDE.md", "claude/CLAUDE.md"),
    ("~/.claude/settings.json", "claude/settings.json"),
    ("~/.claude/skills", "claude/skills"),
    ("~/.claude/hooks", "claude/hooks"),
    ("~/.claude/learnings", "claude/learnings"),
    ("~/.claude/memory", "claude/memory"),
    ("~/.claude/scripts", "claude/scripts"),
    ("~/.claude/output-styles", "claude/output-styles"),
    ("~/.claude/conventions", "claude/conventions"),
    ("~/.git-hooks", "git/hooks"),
    ("~/.gitignore", "git/gitignore"),
    ("~/.gitattributes", "git/gitattributes"),
]

# (git config key, path within the repo). `git config --list` lower-cases the
# variable name, so these are matched folded.
GIT_SETTINGS: list[tuple[str, str]] = [
    ("core.hooksPath", "git/hooks"),
    ("core.excludesFile", "git/gitignore"),
    ("core.attributesFile", "git/gitattributes"),
]

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def points_at(path: str, target: str) -> tuple[bool, str]:
    """Return (ok, human explanation) for one path expected to reach `target`."""
    if not os.path.lexists(path):
        return False, "missing"
    try:
        if os.path.samefile(path, target):
            return True, "ok"
    except OSError:
        # The link exists but leads nowhere — a dangling link, or a target the
        # repo no longer has.
        return False, f"dangling, points at {os.path.realpath(path)}"
    if not os.path.islink(path):
        # A real file or directory sitting where a link belongs. On Windows this
        # is what `ln -s` from Git-Bash leaves behind: a copy that drifts from
        # the repo silently and forever.
        return False, "a real file/directory, not a link — probably a copy"
    return False, f"points at {os.path.realpath(path)}"


def git_globals() -> dict[str, str] | None:
    """Global git config as a dict, or None if git could not be asked at all.

    None and {} are different answers and must not collapse: an empty config is
    three settings genuinely unset, while an unrunnable `git` says nothing about
    them. Reporting the second as "not set" would invent three failures.
    """
    try:
        r = subprocess.run(["git", "config", "--global", "--list"],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode not in (0, 1):  # 1 is git's "nothing to list"
        return None
    out: dict[str, str] = {}
    for line in (r.stdout or "").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip().casefold()] = value.strip()
    return out


def check_all() -> list[tuple[str, bool, str]]:
    """(label, ok, why) for every check, in display order.

    Both modes render from this one list, so a hook message and a by-hand report
    can never disagree about how many things are wrong.
    """
    results: list[tuple[str, bool, str]] = []
    for link, rel in LINKS:
        ok, why = points_at(os.path.expanduser(link), os.path.join(REPO, rel))
        results.append((link, ok, why))

    config = git_globals()
    if config is None:
        results.append(("git config --global", False, "could not run git — the three git settings are unchecked"))
        return results
    for key, rel in GIT_SETTINGS:
        value = config.get(key.casefold())
        if not value:
            results.append((f"git {key}", False, "not set"))
            continue
        ok, why = points_at(os.path.expanduser(value), os.path.join(REPO, rel))
        results.append((f"git {key}", ok, why if ok else f"{why} ({value})"))
    return results


def repair_hint() -> str:
    block = "Linux / macOS" if os.name != "nt" else "Windows (as Administrator)"
    return f"Re-run the '{block}' install block in the repo's README, from the repo root."


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    # An unrecognised argv[1] is a no-op, so a stale command string left in
    # settings.json cannot resurrect a mode that was removed.
    if mode not in ("", "hook"):
        return 0

    results = check_all()
    failed = [(label, why) for label, ok, why in results if not ok]

    if mode == "hook":
        if failed:
            import json
            body = "\n".join(f"  - {label} — {why}" for label, why in failed)
            print(json.dumps({"systemMessage":
                              f"Dotfiles install is incomplete on this machine — "
                              f"{len(failed)} of {len(results)} checks failed. "
                              f"Anything behind these is silently not applied.\n{body}\n{repair_hint()}"}))
        return 0

    print(f"repo: {REPO}\n")
    for label, ok, why in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label:28} {'' if ok else why}")
    print("\nRun from the repo, every line above is a real check. Run through ~/.claude/, the\n"
          "settings.json and hooks lines are circular — the script only got here because they work.")
    if failed:
        print(f"\n{len(failed)} problem(s). {repair_hint()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Never disrupt Claude Code, whatever went wrong here.
        raise SystemExit(0)
