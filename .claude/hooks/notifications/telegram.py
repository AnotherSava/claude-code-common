#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def notify(text: str) -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": text,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()

PROJECT_ROOT = Path.cwd()
PROJECT_NAME = PROJECT_ROOT.name
LAST_ACTIVE_FILE = PROJECT_ROOT / ".claude" / "hooks" / "notifications" / "last_active"
NOTIFICATION_DELAY = 60  # seconds

def last_active_info() -> tuple[bool, str]:
    """Return (was_recently_active, last_prompt)."""
    try:
        age = time.time() - LAST_ACTIVE_FILE.stat().st_mtime
        prompt = LAST_ACTIVE_FILE.read_text(encoding="utf-8").strip()
        return age < NOTIFICATION_DELAY, prompt
    except FileNotFoundError:
        return False, ""

if __name__ == "__main__":
    import json
    if not sys.stdin.isatty():
        hook_input = json.loads(sys.stdin.read())
        message = hook_input.get("message", "")
        if message:
            time.sleep(NOTIFICATION_DELAY)
            active, last_prompt = last_active_info()
            if not active:
                text = f"[{PROJECT_NAME}] {message}"
                if last_prompt:
                    text += f":\n\n{last_prompt[:200]}"
                notify(text)
    elif len(sys.argv) >= 2:
        notify(sys.argv[1])
    else:
        print("Usage: telegram.py 'message text'", file=sys.stderr)
        sys.exit(1)
