#!/usr/bin/env python3
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
if not TOKEN or not CHAT_ID:
    sys.exit(0)

def notify(text: str) -> int | None:
    """Send a message and return the message_id."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": text,
    }
    r = requests.post(url, json=params, timeout=10)
    r.raise_for_status()
    return r.json().get("result", {}).get("message_id")

PROJECT_ROOT = Path.cwd()
PROJECT_NAME = PROJECT_ROOT.name
_project_id = hashlib.md5(str(PROJECT_ROOT).encode()).hexdigest()[:12]
LAST_PROMPT_FILE = Path(tempfile.gettempdir()) / f"claude-last-active-{_project_id}"
NOTIFICATION_FILE = Path(tempfile.gettempdir()) / f"claude-notification-{_project_id}"
NOTIFICATION_DELAY = 60  # seconds

# Session log dir: ~/.claude/projects/<escaped-cwd>/
_escaped_cwd = str(PROJECT_ROOT).replace(":", "-").replace("/", "-").replace("\\", "-")
SESSION_DIR = Path.home() / ".claude" / "projects" / _escaped_cwd

def _session_file_mtime() -> float | None:
    """Return mtime of the most recently modified .jsonl session file."""
    try:
        files = list(SESSION_DIR.glob("*.jsonl"))
        if not files:
            return None
        return max(f.stat().st_mtime for f in files)
    except OSError:
        return None

def was_recently_active() -> bool:
    """Check if the user interacted recently (any interaction, not just prompts)."""
    mtime = _session_file_mtime()
    if mtime is None:
        return False
    return (time.time() - mtime) < NOTIFICATION_DELAY

def last_prompt() -> str:
    """Read the last prompt text recorded by the UserPromptSubmit hook."""
    try:
        return LAST_PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""

def delete_notification() -> None:
    """Delete the last sent notification if one exists."""
    try:
        message_id = NOTIFICATION_FILE.read_text(encoding="utf-8").strip()
        if message_id:
            url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
            requests.post(url, json={"chat_id": CHAT_ID, "message_id": int(message_id)}, timeout=10)
    except (FileNotFoundError, ValueError, requests.RequestException):
        pass
    finally:
        NOTIFICATION_FILE.unlink(missing_ok=True)

if __name__ == "__main__":
    import json
    if not sys.stdin.isatty():
        hook_input = json.loads(sys.stdin.read())
        message = hook_input.get("message", "")
        if message:
            time.sleep(NOTIFICATION_DELAY)
            if not was_recently_active():
                prompt = last_prompt()
                text = f"[{PROJECT_NAME}] {message}"
                if prompt:
                    text += f":\n\n{prompt[:200]}"
                msg_id = notify(text)
                if msg_id:
                    NOTIFICATION_FILE.write_text(str(msg_id), encoding="utf-8")
    elif len(sys.argv) >= 2:
        notify(sys.argv[1])
    else:
        print("Usage: telegram.py 'message text'", file=sys.stderr)
        sys.exit(1)
