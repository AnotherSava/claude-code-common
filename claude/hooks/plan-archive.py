#!/usr/bin/env python3
"""
plan-archive.py — file a freshly approved Claude Code plan into docs/plans/.

One subcommand, reading the hook payload from stdin:

  start — called from PostToolUse[ExitPlanMode]. Finds the just-approved plan
          in ~/.claude/plans/ (by mtime, within a recency window) and moves it
          to <cwd>/docs/plans/<YYYY-MM-DD_HH-MM>_<slug>.md. The slug is derived
          from the plan's first H1 heading, falling back to the original random
          codename (with a warning marker prepended) when no H1 is present.
          Creates the target directory if needed.

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
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

LOG_PATH = Path.home() / ".claude" / "plan-archive.log"
PLANS_DIR = Path.home() / ".claude" / "plans"
RECENCY_WINDOW_SEC = 30  # an ExitPlanMode plan file is typically < 1s old at this hook


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


def derive_slug_from_content(plan_path: Path) -> str | None:
    """Return a slug from the plan's first H1 heading, or None.

    Skips fenced code blocks so `# foo` inside ``` isn't mistaken for a title.
    """
    try:
        in_fence = False
        with plan_path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    title = stripped[2:].strip()
                    if title:
                        s = slugify(title)
                        return s or None
    except OSError:
        return None
    return None


def find_recent_plan() -> Path | None:
    """Return the most recently modified .md in ~/.claude/plans/ within the window, else None."""
    if not PLANS_DIR.exists():
        return None
    now = time.time()
    candidates = []
    for p in PLANS_DIR.glob("*.md"):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if now - mtime < RECENCY_WINDOW_SEC:
            candidates.append((mtime, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


FALLBACK_MARKER = (
    "<!-- plan-archive: no `# H1 Title` was found in this plan, so the archive hook "
    "fell back to the original random codename as the filename slug. Add a descriptive "
    "`# H1` heading and rename the file; then remove this comment. -->\n\n"
)


def prepend_fallback_marker(plan: Path) -> bool:
    """Prepend the H1-missing warning to the plan file. Return True on success."""
    try:
        content = plan.read_text(encoding="utf-8")
    except OSError as e:
        log("fallback_marker_read_error", file=str(plan), error=str(e))
        return False
    if content.startswith(FALLBACK_MARKER):
        return True
    try:
        plan.write_text(FALLBACK_MARKER + content, encoding="utf-8")
        return True
    except OSError as e:
        log("fallback_marker_write_error", file=str(plan), error=str(e))
        return False


def start(payload: dict) -> None:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        log("start_skip_no_cwd", payload_keys=list(payload.keys()))
        return
    plan = find_recent_plan()
    if plan is None:
        log("start_skip_no_recent_plan", cwd=cwd)
        return
    target_dir = Path(cwd) / "docs" / "plans"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log("start_mkdir_error", target=str(target_dir), error=str(e))
        return
    derived_slug = derive_slug_from_content(plan)
    if derived_slug:
        slug = derived_slug
    else:
        slug = plan.stem
        # No H1 found — the filename falls back to the original random codename.
        # Prepend a visible marker so the user (and downstream tools like /commit)
        # can flag the plan for renaming.
        prepend_fallback_marker(plan)
        log("start_fallback_codename", plan=str(plan), slug=slug)
    target = target_dir / f"{timestamp()}_{slug}.md"
    try:
        shutil.move(str(plan), str(target))
        log("start_moved", src=str(plan), dst=str(target), derived=bool(derived_slug))
    except Exception as e:
        log("start_move_error", src=str(plan), dst=str(target), error=str(e))


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
    start(payload)


if __name__ == "__main__":
    main()
