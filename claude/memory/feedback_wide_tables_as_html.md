---
name: feedback_wide_tables_as_html
description: A findings or choice table too wide for the terminal goes to a published HTML page, not a chat markdown table
metadata:
  type: feedback
---

A findings or choice table too wide for the terminal goes to a published HTML page, not a chat markdown table.

**Why:** the terminal (agwinterm, 2026-10-15) drew a wide markdown table with broken borders and overlapping rows, and the user asked "why don't you create an html instead".

**How to apply:** build a self-contained page — a checkbox and a feedback box per row where an answer is wanted, and a Copy answer button that puts the answer on the clipboard as JSON — publish it with `tailnet_publish.py publish`, and hand over the URL (see the tailnet rule in CLAUDE.md). A short, narrow table can stay in chat. For `/review-manual`'s findings, `claude/scripts/review_picker.py` already builds and publishes this page outside agterm.
