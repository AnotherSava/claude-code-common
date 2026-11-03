---
name: feedback_wide_tables_as_html
description: A findings or choice table too wide for the terminal goes to a published HTML page, not a chat markdown table
metadata:
  type: feedback
---

A findings or choice table too wide for the terminal goes to a published HTML page, not a chat markdown table.

**Why:** the terminal (agwinterm, 2026-10-15) drew a wide markdown table with broken borders and overlapping rows, and the user asked "why don't you create an html instead".

**How to apply:** where an answer is wanted, write the rows as a spec for `claude/scripts/review_picker.py` (format in its docstring) and run it: each row gets its choices preset to the recommendation and a note box, and the page opens as a blocking agterm overlay or, outside agterm, is published on the tailnet with a Copy answer button. A table that only informs gets published as a plain page with `tailnet_publish.py publish`, and the URL handed over (see the tailnet rule in CLAUDE.md). A short, narrow table can stay in chat.
