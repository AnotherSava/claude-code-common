#!/usr/bin/env python3
import hashlib
import json
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

def delete_notifications() -> None:
    """Delete all pending notifications."""
    try:
        lines = NOTIFICATION_FILE.read_text(encoding="utf-8").strip().splitlines()
        url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
        for line in lines:
            msg_id = line.strip()
            if msg_id:
                try:
                    requests.post(url, json={"chat_id": CHAT_ID, "message_id": int(msg_id)}, timeout=10)
                except (ValueError, requests.RequestException):
                    pass
    except FileNotFoundError:
        pass
    finally:
        NOTIFICATION_FILE.unlink(missing_ok=True)

def last_assistant_ends_with_question(transcript_path: str) -> bool:
    """Check if the last assistant text block in the session ends with '?'."""
    try:
        last_text = ""
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                msg = json.loads(line).get("message", {})
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    last_text = content.strip()
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text", "").strip():
                            last_text = block["text"].strip()
        return last_text.endswith("?")
    except (OSError, json.JSONDecodeError):
        return False


def format_notification(hook_input: dict) -> str | None:
    """Build notification text based on notification type. Returns None to skip."""
    notification_type = hook_input.get("notification_type", "")
    message = hook_input.get("message", "")
    transcript_path = hook_input.get("transcript_path", "")

    if notification_type == "permission_prompt":
        # "Claude needs your permission to use Bash" -> "Needs approval: Bash"
        tool = message.rsplit("use ", 1)[-1] if "use " in message else "a tool"
        return f"[{PROJECT_NAME}] Needs approval: {tool}"

    if notification_type == "idle_prompt":
        if last_assistant_ends_with_question(transcript_path):
            label = "Has a question"
        else:
            label = "Done"
        prompt = last_prompt()
        text = f"[{PROJECT_NAME}] {label}"
        if prompt:
            text += f":\n\n{prompt[:200]}"
        return text

    # plan_approval, generic attention, or unknown
    if message:
        return f"[{PROJECT_NAME}] {message}"
    return None


if __name__ == "__main__":
    if not sys.stdin.isatty():
        hook_input = json.loads(sys.stdin.read())
        text = format_notification(hook_input)
        if text:
            time.sleep(NOTIFICATION_DELAY)
            if not was_recently_active():
                msg_id = notify(text)
                if msg_id:
                    with NOTIFICATION_FILE.open("a", encoding="utf-8") as f:
                        f.write(f"{msg_id}\n")
    elif len(sys.argv) >= 2:
        notify(sys.argv[1])
    else:
        print("Usage: telegram.py 'message text'", file=sys.stderr)
        sys.exit(1)
