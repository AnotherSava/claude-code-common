---
name: feedback_amend_the_published_comment
description: A correction to something you already published goes into that text by editing it, never into a second comment stacked beneath it
metadata:
  type: feedback
---

When text you already published turns out wrong or incomplete, edit it in place rather than posting a follow-up. A reader then meets the corrected claim once, where the argument lives; a correction stacked underneath leaves the wrong version as the thing most people read, and splits one finding across two posts. Platforms keep an edit history, so nothing is hidden by it.

**Why:** 2026-09-30, correcting my own comment on an upstream issue, I drafted a follow-up beginning "Correction and an addition to my previous comment"; the user replied "replace a comment instead of new one".

**How to apply:** rewrite the whole text as it should now stand — one merged standalone version, not the original plus a correction paragraph — and show that full text for approval before replacing it, since it is different text from what was approved the first time. On GitHub the edit is `gh api -X PATCH /repos/<owner>/<repo>/issues/comments/<id> -F body=@<file>`; `gh issue comment` can only append. Governed by the same draft-show-confirm rule as the original, in [[feedback_no_guessed_facts]]'s neighbourhood — see CLAUDE.md's Outward Communication.
