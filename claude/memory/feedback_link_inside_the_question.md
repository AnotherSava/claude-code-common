---
name: feedback_link_inside_the_question
description: When a choice depends on a page or file the user must open first, put its link inside the question box or ask in plain text — the question UI covers the text above it
metadata:
  type: feedback
---

When the user has to look at something before they can answer — a contact sheet, a comparison page, a report — the link has to be where they are looking when the question arrives. The AskUserQuestion box covers the reply text before it, so a link placed only in that text is out of sight at exactly the moment it is needed.

2026-09-23/24: twice in one session a report link sat in the text above a question box. The first time the user rejected the tool call and asked "have you created a report on screenshots?"; the second time they rejected it and asked "give me a link". Each cost a round trip to hand over a link that had already been written.

**Why:** the question box is modal in practice — the user reads it and answers it, and what scrolled above it is not part of what they see.

**How to apply:** when a question depends on an artifact to open, put the `file:///` link in the question text or an option's description, or skip the tool and ask in plain text with the link in the closing paragraph. Related: [[feedback_show_the_artifact_with_the_ask]], [[feedback_image_report_always]].
