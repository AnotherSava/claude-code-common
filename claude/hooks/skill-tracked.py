#!/usr/bin/env python3
"""PostToolUse backstop: a newly written SKILL.md that git is ignoring.

A skills directory is normally covered by an ignore-everything-then-allowlist rule
(`claude/skills/*` plus one `!claude/skills/<name>/` line each). Miss the allowlist
line and the new skill is invisible: it never shows up in `git status`, so nothing
signals the omission, and the only copy stays on the machine that wrote it. This
has silently lost skills more than once — they get swept up later in a catch-up
"register new skills" commit, if anyone notices at all.

The `/skill` skill documents the check, but it sits far below the step that creates
the directory and relies on remembering to run it at the end. This hook is the
deterministic net: it asks git the moment a SKILL.md is written, and reports the
exact file, line and pattern doing the ignoring.

Registered on `Write` only, gated by `"if": "Write(//**/SKILL.md)"`. A matcher scopes
by tool *name* alone, and this hook is not worth ~200ms of interpreter startup on
every edit in a session, so the `if` rule does the path filtering *before* anything
spawns — measured: a non-SKILL.md write starts no process at all. That pattern must
stay root-anchored (`//`); an unanchored `**/SKILL.md` matches nothing and silently
disables the hook. `Write` alone is sufficient because a SKILL.md can only come into
existence through it; Edit would only re-flag skills the audit command already finds.

The basename check below is therefore redundant with the `if` rule, and kept: it makes
the script correct on its own if the matcher is ever widened. Silent (exit 0, no
output) unless the skill is actually ignored.
"""
import json
import os
import subprocess
import sys

GIT_TIMEOUT = 5


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True, timeout=GIT_TIMEOUT,
    )


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never break a tool call on a parse hiccup

    tool_input = data.get("tool_input") or {}
    response = data.get("tool_response") or {}
    path = response.get("filePath") or tool_input.get("file_path")
    if not isinstance(path, str) or os.path.basename(path) != "SKILL.md":
        return 0

    # Resolve first: ~/.claude/skills is a symlink into the dotfiles repo, and
    # git refuses a path that sits outside the worktree it is asked about.
    skill_dir = os.path.dirname(os.path.realpath(path))
    if not os.path.isdir(skill_dir):
        return 0

    try:
        top = _git(skill_dir, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return 0  # not a git repo — nothing to be ignored by
        repo = top.stdout.strip()
        rel = os.path.relpath(skill_dir, repo).replace(os.sep, "/") + "/"
        check = _git(repo, "check-ignore", "-v", rel)
    except (OSError, subprocess.SubprocessError):
        return 0

    # Exit 0 means ignored. Anything else — 1 (not ignored) or 128 (bad path) —
    # is not a confirmed problem, and 128 must not be read as success.
    if check.returncode != 0:
        return 0

    name = os.path.basename(skill_dir)
    citation = check.stdout.strip().split("\t")[0] or "the ignore file"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"The `{name}` skill is gitignored — it will never be committed, and the only "
                f"copy is on this machine. Ignored by {citation}. Add an un-ignore line for it "
                f"beside its siblings (`!{rel}` in that file's repo-relative form), then confirm "
                f"with `git check-ignore -v {rel}` until it exits 1. Do this now; it is silent "
                f"otherwise — an ignored skill never appears in `git status`."
            ),
        },
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
