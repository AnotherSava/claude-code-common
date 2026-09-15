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
      assistant to start memo N, bound to that very prompt. A memo carrying a
      `platform:` this machine is not gets an extra clause: do the portable
      part here and route the rest to the live session on that box.

State lives per-session (keyed by session_id) in the system temp dir. Only
session-start reads the backlog, and it imports `memos.py` to do it rather
than re-implementing the parse — the status line refreshes every couple of
seconds and must stay off that path entirely.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# Emit UTF-8 regardless of the platform console codepage so em-dashes in memo titles survive
# (Windows defaults stdout to cp1252, which would mangle them in the status line).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PICK_RE = re.compile(r"^\s*(?:memo|start|do|pick|work on)?\s*#?\s*(\d+)\s*[.)]?\s*$", re.I)
MAX_SHOWN = 3


def _payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    # Valid JSON of the wrong shape reaches every caller as a dict-shaped thing that is not one.
    return payload if isinstance(payload, dict) else {}


def _state_path(payload: dict) -> str:
    sid = payload.get("session_id") or "default"
    return os.path.join(tempfile.gettempdir(), f"claude-memo-state-{sid}.json")


def _repo_root(base: str) -> str:
    """Resolve the repo root from `base`, matching how memos.py locates the backlog.

    The /memo skill writes under `<git toplevel>/.claude/memos/`, so resolve the
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


def _open_memos(payload: dict) -> list[dict]:
    base = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    # Imported here rather than at module scope so the status-line mode never pays for it.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "memo"))
    # Reading a directory of files has more ways to fail than reading one did — an unreadable
    # file, a corrupt encoding, a broken import. The never-raise contract wants every one of
    # them swallowed: a backlog that fails to render is a missing reminder, never a failed hook.
    try:
        import memos
        # The `tag` and `elsewhere` fields are resolved once, here, and stored. Deciding which platform this
        # is belongs on the session-start path, which already forks git and imports this module —
        # the status line re-runs every couple of seconds and must read one small file and nothing
        # else (see skills/hooks/references/performance.md).
        return [{"slug": m.slug, "title": m.title, "tag": m.tag, "elsewhere": m.elsewhere}
                for m in memos.open_memos(_repo_root(base))]
    except Exception:
        return []


def _read_state(payload: dict) -> list[dict]:
    try:
        with open(_state_path(payload), encoding="utf-8") as fh:
            memos = json.load(fh).get("memos", [])
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        return []
    return memos if isinstance(memos, list) else []


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
    memos = _open_memos(payload)
    if not memos:
        _drop_state(payload)
        return
    with open(_state_path(payload), "w", encoding="utf-8") as fh:
        json.dump({"memos": memos}, fh)


def statusline(payload: dict) -> None:
    memos = _read_state(payload)
    if not memos:
        return
    rows = [f"Memos ({len(memos)}) - pick one or start fresh:"]
    for i, memo in enumerate(memos[:MAX_SHOWN], 1):
        # Truncate the title first, then prepend the tag — the other order spends the budget on
        # the marker and can cut the very thing the marker is about.
        rows.append(f" {i}. {memo.get('tag', '')}{memo.get('title', '')[:90]}")
    if len(memos) > MAX_SHOWN:
        # Count only what is behind the `+N`. The rows above carry their own tags and are already
        # on screen, so including them here would be the duplicate signal to avoid — and without
        # this the bar is the one surface where a binding never shows at all, since the backlog is
        # newest-first and a bound memo is usually not among the newest three.
        hidden = memos[MAX_SHOWN:]
        elsewhere = sum(1 for m in hidden if m.get("elsewhere"))
        note = f" ({elsewhere} not for this machine)" if elsewhere else ""
        rows.append(f" +{len(hidden)} more{note} - /memo")
    print("\n".join(rows))


def on_prompt(payload: dict) -> None:
    memos = _read_state(payload)
    _drop_state(payload)  # any interaction ends the bar reminder
    if not memos:
        return
    match = PICK_RE.match(_prompt_text(payload))
    if not match:
        return
    n = int(match.group(1))
    if not 1 <= n <= len(memos):
        return
    memo = memos[n - 1]
    # No numeric fallback. This state was written at session start, while `memos.py show <n>` and
    # `done <n>` resolve a number against the live listing at command time — so any add or close
    # since then makes the bar's number name a different memo, and `done` would move the wrong
    # file. A slug is stable; without one there is nothing safe to inject.
    slug = memo.get("slug")
    if not slug:
        return
    context = (
        f'The user selected memo #{n} from the status-bar backlog: "{memo.get("title", "")}". Read it in '
        f'full with `python ~/.claude/skills/memo/memos.py show {slug}` — the title is only '
        "its first line — then start working on it now as a fresh task. Once it's genuinely done, run "
        f'`python ~/.claude/skills/memo/memos.py done {slug}` to move it into done/.'
    )
    if memo.get("elsewhere"):
        context += (
            " This memo is tagged for the other platform, so the work it names cannot be finished on this "
            "machine. Do whatever part of it is portable here, then route the rest to the live session on "
            "that box as described in `~/.claude/memory/peer_messaging.md` — leaving it in the backlog just "
            "defers it to whoever next reads it, on whichever machine they happen to be on. Close it only "
            "if the portable part was the whole memo."
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
