---
name: feedback_clipboard_text_unwrapped
description: Prose put on the clipboard for a web form goes unwrapped and unformatted — one line per paragraph, no markdown
metadata:
  type: feedback
---

When prose goes on the clipboard for the user to paste into a web form (a support request, a contact form, a
profile field), copy it as plain text with each paragraph on a single line: no hard wraps at 72 or 110 columns, no
markdown, no subject line folded into the body.

**Why:** asked on 2026-11-13 whether to copy an approved Brevo support request to the clipboard as it stood, the
user answered "yes, but without formatting". The draft on screen was plain text under a `Subject:` line,
hard-wrapped at about 70 columns. Reading "formatting" as those wraps, and extending it to markdown, is an
interpretation the user did not state: a form field reflows text itself, so wrapped lines paste in as ragged short
ones. The unwrapped copy was pasted and submitted without comment.

**How to apply:** show the draft wrapped for reading, as usual. Unwrap it only when it goes on the clipboard, and
change nothing else, since the approval covered the words. Give a separate field such as the subject on its own.
Related: [[feedback_route_output_not_paste]].
