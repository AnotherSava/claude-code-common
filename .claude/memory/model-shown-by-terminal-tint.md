---
name: model-shown-by-terminal-tint
description: A session's non-default model is shown by the dashboard tinting its terminal row purple, not by a status line; decided 2026-11-23, don't re-propose a model status line
metadata:
  type: project
---

A Claude session on a model other than the default (`ANTHROPIC_MODEL` in `claude/settings.json`) is marked by the
dashboard tinting its sidebar row purple in agterm, and in agwinterm once that fork has a tint command. The model tint
wins over attach.sh's remote-tab tint, and the dashboard owns both. This repo's part is the `PostModelSwitch` entry
that runs the dashboard's `claude_hook.py`.

**Why:** a model status line was built and tried on 2026-11-23 and dropped. Under the fullscreen renderer a status line
that prints nothing still keeps an empty row (`learnings/claude-code-status-line.md`), and the user tried the classic
renderer and preferred fullscreen.

**How to apply:** don't re-propose a status line for showing the model. A change to how the model is shown goes to the
dashboard repo's session.
