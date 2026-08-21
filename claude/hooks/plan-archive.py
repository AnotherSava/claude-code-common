#!/usr/bin/env python3
"""
plan-archive.py — move Claude Code plans into the project's docs/plans/ folder.

Two subcommands, both read the hook payload from stdin:

  start — called from PostToolUse[ExitPlanMode]. Finds the just-approved plan
          in ~/.claude/plans/ (by mtime, within a recency window) and moves it
          to <cwd>/docs/plans/<YYYY-MM-DD_HH-MM>_<slug>.md. The slug is derived
          from the plan's first H1 heading, falling back to the original random
          codename (with a warning marker prepended) when no H1 is present.
          Creates the target directory if needed.

  done  — called from Notification. On an "idle_prompt" whose last assistant
          text does not end with '?', consider each active plan in
          <cwd>/docs/plans/ for archiving into <cwd>/docs/plans/completed/.

          Going idle is NOT evidence that a plan was executed, so idleness only
          decides *when* to look — never whether to move. Completion has to be
          stated in the plan itself, one of:
            * an explicit `<!-- plan-archive: done -->` marker, or
            * a task list whose boxes are all checked.
          A plan with open `- [ ]` items is in flight and is left alone. A plan
          with neither marker nor checkboxes carries no verdict to read, so it
          waits until it is unambiguously stale (NO_SIGNAL_MIN_AGE_SEC).
          Nothing is lost by skipping: this runs on every idle prompt, so a plan
          archives at the first idle moment after it says it is finished.

All errors are logged to ~/.claude/plan-archive.log. The script never raises —
a failed archive is logged and ignored so the hook cannot disrupt Claude Code.

See ~/.claude/learnings/claude-code-integration.md for the classification
rationale (done vs awaiting, the ?-heuristic, notification_type values).
"""
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

# Completion signals read out of the plan body (see `done`).
DONE_MARKER_RE = re.compile(r"<!--\s*plan-archive:\s*done\s*-->", re.IGNORECASE)
UNCHECKED_TASK_RE = re.compile(r"^\s*[-*]\s+\[ \]", re.MULTILINE)
CHECKED_TASK_RE = re.compile(r"^\s*[-*]\s+\[[xX]\]", re.MULTILINE)

# Fallback for a plan that states nothing — no marker, no task list. There is no
# verdict to read, so age is the only remaining signal: a plan untouched for this
# long is finished or abandoned, either way not in flight. Deliberately generous;
# a late archive costs nothing, a premature one silently mislabels live work.
NO_SIGNAL_MIN_AGE_SEC = 7 * 24 * 60 * 60  # 7 days


def log(event: str, **data) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "event": event, **data}) + "\n")
    except Exception:
        pass


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def last_assistant_ends_with_question(transcript_path) -> bool:
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return False
    try:
        last_text = ""
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    msg = json.loads(line).get("message", {}) or {}
                except Exception:
                    continue
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    last_text = content.strip()
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if isinstance(text, str) and text.strip():
                                last_text = text.strip()
        return last_text.endswith("?")
    except OSError:
        return False


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


def body_outside_fences(plan_path: Path) -> str | None:
    """Return the plan's text with fenced code blocks removed, or None if unreadable.

    Checkboxes and markers quoted inside a ``` fence are documentation, not the
    plan's own state — counting them would read an example as a verdict.
    """
    try:
        lines = []
        in_fence = False
        with plan_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if not in_fence:
                    lines.append(line)
        return "".join(lines)
    except OSError:
        return None


def completion_signal(plan_path: Path) -> tuple[bool, str]:
    """Decide whether a plan declares itself finished. Returns (archive?, reason).

    The reason is logged either way, so a plan that stays put says why.
    """
    body = body_outside_fences(plan_path)
    if body is None:
        return False, "unreadable"
    if DONE_MARKER_RE.search(body):
        return True, "done_marker"
    unchecked = len(UNCHECKED_TASK_RE.findall(body))
    if unchecked:
        return False, f"open_tasks={unchecked}"
    checked = len(CHECKED_TASK_RE.findall(body))
    if checked:
        return True, f"all_tasks_checked={checked}"
    try:
        age = int(time.time() - plan_path.stat().st_mtime)
    except OSError:
        return False, "unreadable_mtime"
    if age < NO_SIGNAL_MIN_AGE_SEC:
        return False, f"no_signal_age={age}s"
    return True, f"no_signal_stale_age={age}s"


def done(payload: dict) -> None:
    # Checks are ordered cheapest-first on purpose. Reading the transcript means
    # streaming the whole session JSONL to EOF, so it must come last — most
    # projects have no docs/plans/ at all, and paying that parse on every idle
    # notification only to return is the cost this ordering avoids.
    if payload.get("notification_type") != "idle_prompt":
        return
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return
    plans_dir = Path(cwd) / "docs" / "plans"
    if not plans_dir.exists():
        return
    actives = [p for p in plans_dir.glob("*.md") if p.is_file()]
    if not actives:
        return
    transcript_path = payload.get("transcript_path")
    if last_assistant_ends_with_question(transcript_path):
        log("done_skip_has_question", transcript=transcript_path)
        return
    completed_dir = plans_dir / "completed"
    for plan in actives:
        archive, reason = completion_signal(plan)
        if not archive:
            log("done_skip_unfinished", plan=str(plan), reason=reason)
            continue
        # Created only once something is actually going to move, so a project
        # that never finishes a plan doesn't grow an empty completed/ folder.
        try:
            completed_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log("done_mkdir_error", target=str(completed_dir), error=str(e))
            return
        target = completed_dir / plan.name
        try:
            shutil.move(str(plan), str(target))
            log("done_moved", src=str(plan), dst=str(target), reason=reason)
        except Exception as e:
            log("done_move_error", src=str(plan), dst=str(target), error=str(e))


def main() -> None:
    if len(sys.argv) < 2:
        return
    cmd = sys.argv[1]
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if cmd == "start":
        start(payload)
    elif cmd == "done":
        done(payload)


if __name__ == "__main__":
    main()
