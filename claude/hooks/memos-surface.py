#!/usr/bin/env python3
"""Memo backlog surfacing for Claude Code hooks + status line.

The open `/memo` backlog appears as a transient status-bar reminder after a
session start / clear, and disappears the moment the user interacts. When the
user's first message is just a number, it selects that memo to work on — and
the mapping is injected right onto that message, so it's acted on reliably
(rather than relying on lingering session context, which a bare "1" ignores).

Three modes, selected by argv[1]:

  (default / "session-start")  SessionStart hook (startup|clear). Writes a
      per-session state file with the open memos (newest first). Injects NO
      chat context on purpose — the status bar is the reminder, so the model
      never greets with or pushes the backlog.

  "statusline"   Status line command. Renders the compact backlog from the
      state file when it exists, otherwise prints nothing.

  "on-prompt"    UserPromptSubmit hook. Clears the state (the bar reminder is
      done once the user acts). If the message is just a number N — or
      "memo N" / "start N" / "do N" / "pick N" — injects context telling the
      assistant to start memo N, bound to that very prompt.

State lives per-session (keyed by session_id) in the system temp dir.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# Emit UTF-8 regardless of the platform console codepage so em-dashes in memo text survive
# (Windows defaults stdout to cp1252, which would mangle them in the status line).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OPEN_RE = re.compile(r"^- \[ \] \d{4}-\d\d-\d\d \d\d:\d\d — (.*)$")
PICK_RE = re.compile(r"^\s*(?:memo|start|do|pick|work on)?\s*#?\s*(\d+)\s*[.)]?\s*$", re.I)
MAX_SHOWN = 3


def _payload() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def _state_path(payload: dict) -> str:
    sid = payload.get("session_id") or "default"
    return os.path.join(tempfile.gettempdir(), f"claude-memo-state-{sid}.json")


def _repo_root(base: str) -> str:
    """Resolve the repo root from `base`, matching how memos.py locates the file.

    The /memo skill writes to `<git toplevel>/.claude/memos.md`, so resolve the
    same way — otherwise launching from a subdirectory makes the writer (git
    root) and reader disagree and the backlog vanishes. Falls back to `base`.
    """
    try:
        out = subprocess.run(["git", "-C", base, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    return base


def _open_ideas(payload: dict) -> list[str]:
    base = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    memos_path = os.path.join(_repo_root(base), ".claude", "memos.md")
    try:
        with open(memos_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    ideas = [m.group(1) for m in (OPEN_RE.match(ln) for ln in lines) if m]
    return list(reversed(ideas))  # newest first, matching the /memo skill's numbering


def _read_state(payload: dict) -> list[str]:
    try:
        with open(_state_path(payload), encoding="utf-8") as fh:
            return json.load(fh).get("ideas", [])
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        return []


def _drop_state(payload: dict) -> None:
    try:
        os.remove(_state_path(payload))
    except OSError:
        pass


def _prompt_text(payload: dict) -> str:
    for key in ("prompt", "user_prompt", "message", "text"):
        val = payload.get(key)
        if isinstance(val, str):
            return val
    return ""


def session_start(payload: dict) -> None:
    ideas = _open_ideas(payload)
    if not ideas:
        _drop_state(payload)
        return
    with open(_state_path(payload), "w", encoding="utf-8") as fh:
        json.dump({"ideas": ideas}, fh)


def statusline(payload: dict) -> None:
    ideas = _read_state(payload)
    if not ideas:
        return
    rows = [f"Memos ({len(ideas)}) - pick one or start fresh:"]
    for i, idea in enumerate(ideas[:MAX_SHOWN], 1):
        rows.append(f" {i}. {idea[:90]}")
    if len(ideas) > MAX_SHOWN:
        rows.append(f" +{len(ideas) - MAX_SHOWN} more - /memo")
    print("\n".join(rows))


def on_prompt(payload: dict) -> None:
    ideas = _read_state(payload)
    _drop_state(payload)  # any interaction ends the bar reminder
    if not ideas:
        return
    m = PICK_RE.match(_prompt_text(payload))
    if not m:
        return
    n = int(m.group(1))
    if not 1 <= n <= len(ideas):
        return
    context = (
        f'The user selected memo #{n} from the status-bar backlog: "{ideas[n - 1]}". Start working on '
        "it now as a fresh task. Once it's genuinely done, flip its `- [ ]` to `- [x]` in "
        ".claude/memos.md (match it by this text)."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context},
    }))


def main() -> None:
    # No arg = the SessionStart hook. An unknown *explicit* arg is a no-op, so a stale
    # command string from a not-yet-restarted session (e.g. the old "clear-flag") can't
    # accidentally re-arm the bar by falling through to session-start.
    mode = sys.argv[1] if len(sys.argv) > 1 else "session-start"
    handler = {"session-start": session_start, "statusline": statusline, "on-prompt": on_prompt}.get(mode)
    if handler:
        handler(_payload())


if __name__ == "__main__":
    main()
