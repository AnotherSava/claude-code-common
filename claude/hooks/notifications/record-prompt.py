#!/usr/bin/env python3
"""UserPromptSubmit hook: record the last prompt and dismiss any pending notification."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

try:
    data = json.loads(sys.stdin.read())
    prompt = data.get("prompt", "") if isinstance(data, dict) else ""
except json.JSONDecodeError:
    sys.exit(0)

project_id = hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:12]
last_prompt_file = Path(tempfile.gettempdir()) / f"claude-last-active-{project_id}"
if len(prompt) > 10:
    last_prompt_file.write_text(prompt, encoding="utf-8")
    last_prompt_file.chmod(0o600)

# Delete pending Telegram notification if user is back
notification_file = Path(tempfile.gettempdir()) / f"claude-notification-{project_id}"
if notification_file.exists():
    try:
        import os
        import requests
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent / ".env")
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        message_id = notification_file.read_text(encoding="utf-8").strip()
        if token and chat_id and message_id:
            requests.post(f"https://api.telegram.org/bot{token}/deleteMessage", json={"chat_id": chat_id, "message_id": int(message_id)}, timeout=10)
    except Exception:
        pass
    finally:
        notification_file.unlink(missing_ok=True)
