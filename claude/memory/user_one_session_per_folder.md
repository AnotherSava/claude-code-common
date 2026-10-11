---
name: user_one_session_per_folder
description: The user runs one Claude Code session per project folder and never uses --fork-session migrations
metadata:
  type: user
---

The user runs one Claude Code session per project folder and never uses `--fork-session` migrations; on Windows a new tmux session joins the existing one. A second live session in a folder is a fault to report, not a workflow to serve. (Stated 2026-10-10 while designing the dashboard's row membership.)
