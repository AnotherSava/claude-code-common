#!/usr/bin/env python3
"""
plan-archive.py — file a freshly approved Claude Code plan into docs/plans/.

One subcommand, reading the hook payload from stdin:

  start — called from PostToolUse[ExitPlanMode]. Writes the approved plan text
          from the payload's `tool_response.plan` to
          <repo root>/docs/plans/<YYYY-MM-DD_HH-MM>_<slug>.md, or to
          <cwd>/docs/plans/ outside a git repo. The slug is derived from the
          plan's first H1 heading, falling back to the stem of the session's
          plan file (`tool_response.filePath`, a random codename) with a warning
          marker prepended when no H1 is present. Creates the target directory
          if needed.

The plan comes from the payload rather than from the newest file in
~/.claude/plans/: that directory is shared by every session, so a guess by mtime
can file one session's plan into another's repo. Nothing in ~/.claude/plans/ is
moved or edited — Claude Code keeps one plan file per session and asks the model
to edit it incrementally, so anything written there would carry into that
session's next plan. The file there stays as Claude Code left it, so a skipped
repo or a cleaned working tree still leaves that copy behind.

A fork or a clone of someone else's project gets nothing filed: its docs/plans/
may hold the upstream author's own design docs, and a fork's commits travel
upstream in a pull request, so a filed plan would end up proposed to a repo that
is not the user's. Whose repo it is comes from the conventions engine, the same
answer /adopt and the session-start conventions check get.

The other half of a plan's lifecycle — moving a finished plan into
docs/plans/completed/ — is a step in the `commit` skill, not a hook. It used to
be a `done` subcommand on Notification[idle_prompt], and that had no way to tell
a plan it had filed itself from a document the repo tracks upstream: it globbed
every .md under docs/plans/ and moved whatever declared itself finished. In a
third-party clone that silently deleted tracked files between turns, with
nothing in the transcript to explain it. Archiving at commit time puts the move
in front of a reviewer and never touches a repo nobody commits to. Anything
still invoking `done` reaches the no-op below, which is deliberate: hooks load
at session start, so sessions predating this change keep calling it.

All errors are logged to ~/.claude/plan-archive.log. The script never raises —
a failed archive is logged and ignored so the hook cannot disrupt Claude Code.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath

# Reached the way `conventions-check.py` reaches it; `abspath` rather than `realpath` so this works
# whether the hook was invoked through ~/.claude/hooks or straight out of the checkout.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conventions"))

try:
    import engine  # noqa: E402 — needs the sys.path line above
except BaseException:
    # The never-raise guard cannot reach a module-level import. Without the engine nothing can say
    # whose repo this is, so `start` files nothing; the plan is still in ~/.claude/plans/.
    engine = None

LOG_PATH = Path.home() / ".claude" / "plan-archive.log"


def log(event: str, **data) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "event": event, **data}) + "\n")
    except Exception:
        pass


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def slugify(text: str) -> str:
    """Kebab-case ASCII slug, capped at 60 chars."""
    text = re.sub(r"[`*\"']", "", text)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug


def derive_slug_from_content(text: str) -> str | None:
    """Return a slug from the plan's first H1 heading, or None.

    Skips fenced code blocks so `# foo` inside ``` isn't mistaken for a title.
    """
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            if title:
                return slugify(title) or None
    return None


FALLBACK_MARKER = (
    "<!-- plan-archive: no `# H1 Title` was found in this plan, so the archive hook "
    "fell back to the original random codename as the filename slug. Add a descriptive "
    "`# H1` heading and rename the file; then remove this comment. -->\n\n"
)


def plans_dir_for(cwd: str) -> Path | None:
    """Where a plan approved in `cwd` is filed, or None when this is not the user's repo to file into."""
    if engine is None:
        log("start_skip_no_engine", cwd=cwd)
        return None
    root = engine.repo_root(cwd)
    if root is not None:
        owner = engine.is_third_party(root) or engine.fork_of(root)
        if owner is not None:
            log("start_skip_not_ours", root=root, owner=owner)
            return None
    return Path(root or cwd) / "docs" / "plans"


def start(payload: dict) -> None:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        log("start_skip_no_cwd", payload_keys=list(payload.keys()))
        return
    response = payload.get("tool_response")
    plan = response.get("plan") if isinstance(response, dict) else None
    if not isinstance(plan, str) or not plan.strip():
        log("start_skip_no_plan", cwd=cwd, response_type=type(response).__name__)
        return
    target_dir = plans_dir_for(cwd)
    if target_dir is None:
        return
    slug = derive_slug_from_content(plan)
    derived = slug is not None
    if not derived:
        # No H1 — the filename falls back to the session's codename, and the filed copy carries a
        # visible marker so the user (and /commit) can flag it for renaming. `filePath` is written
        # by Claude Code on whichever OS it runs, and PureWindowsPath splits on both separators.
        source = response.get("filePath")
        slug = slugify(PureWindowsPath(source).stem) if isinstance(source, str) else ""
        if not slug:
            log("start_skip_no_slug", cwd=cwd, file_path=source)
            return
        plan = FALLBACK_MARKER + plan
        log("start_fallback_codename", slug=slug)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log("start_mkdir_error", target=str(target_dir), error=str(e))
        return
    target = target_dir / f"{timestamp()}_{slug}.md"
    try:
        # `newline=""` keeps the plan's own line endings; `write_text` takes that argument only from 3.10.
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(plan if plan.endswith("\n") else plan + "\n")
        log("start_filed", dst=str(target), derived=derived)
    except OSError as e:
        log("start_write_error", dst=str(target), error=str(e))


def main() -> None:
    # Dispatch on the subcommand rather than running unconditionally: a session
    # that started before the `done` hook was removed still has it registered
    # and will keep invoking it, and that call must do nothing rather than fall
    # through to `start`.
    if len(sys.argv) < 2 or sys.argv[1] != "start":
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        start(payload if isinstance(payload, dict) else {})
    except Exception as e:
        log("start_error", error=repr(e))


if __name__ == "__main__":
    main()
