---
created: 2026-09-18 13:16:15
platform: windows
---

# Pull the dotfiles on the Windows machine so the link guard and the fixed link-project-memory.sh take effect there

Until that pull, that machine runs the old `claude/scripts/link-project-memory.sh`, which creates a directory junction because it needs no elevation — and the `PreToolUse` guard that would now refuse one is not registered there either. So wiring a new project's memory there before the pull re-creates exactly the links repaired on 2026-09-18: Windows will not follow a reparse point created by a non-administrator (RedirectionGuard, WinError 448), and it refuses a symlink as readily as a junction.

What was already repaired that day, so this is about recurrence and not about a live breakage: `~/.claude/conventions`, `~/.claude/memory` and `~/.claude/scripts`, plus all 19 project memory caches, each recreated as a symlink from an elevated session.

Next step there: pull the dotfiles repo, then confirm with `python -S ~/.claude/hooks/check-install.py` that all twelve links report ok — that check now names a link the OS refuses instead of crashing on it. Background and the measurements are in `claude/learnings/git-bash-windows-symlinks.md`.
