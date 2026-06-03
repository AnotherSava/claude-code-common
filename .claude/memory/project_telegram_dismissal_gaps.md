---
name: Telegram notification dismissal gaps
description: Known cases where claude/hooks/notifications/ leaves Telegram messages stale, and the architectural constraint behind them
type: project
---
Telegram notification dismissal in `claude/hooks/notifications/` (telegram.py + record-prompt.py) only fires on `UserPromptSubmit` and is keyed per-project (md5 hash of cwd). This leaves three known gaps:

1. **Permission approvals via terminal click** — clicking "Allow" on a `permission_prompt` in the Claude UI does not fire `UserPromptSubmit`, so the corresponding Telegram notification stays in the chat until the user later types a real prompt in that project.
2. **Cross-project** — typing in project A doesn't dismiss notifications from project B because `NOTIFICATION_FILE` is keyed by the per-project hash.
3. **Manual notifications** — messages sent via the `telegram.py 'message'` argv path (e.g. `rd.sh --review` ✅/❌) are never recorded in `NOTIFICATION_FILE`, so they're never auto-deleted.

**Why:** the dismissal model assumes "user is back" == "user typed a new prompt in this project". That covers the common idle_prompt → reply case but not the other entry points to a session.

**How to apply:** before adding new Notification types or new hook integrations, decide which dismissal trigger covers them. Discussed remediation options:
- Option 1 (smallest): add a `Stop` hook that runs the same dismissal logic — catches the approval-then-idle case once Claude winds down.
- Option 2: poll session jsonl mtime from inside telegram.py after sending, self-delete on activity. More responsive but leaves orphan Python processes.
- Option 3: single-daemon design that watches all session dirs and dismisses across projects. Bigger lift; only earns its keep if also tracking manual notifications and surviving terminal closes.
