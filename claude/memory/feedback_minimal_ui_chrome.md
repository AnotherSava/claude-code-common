---
name: feedback_minimal_ui_chrome
description: Strip UI chrome that repeats or explains what the interface already shows — no duplicate state signals, no field help text, no card blurbs
metadata:
  type: feedback
---

Strip UI chrome that repeats or explains what the interface already shows. Corrections given while building the What's Next Settings screen (2026-08-05), each one reversing something I had added:

- **Don't signal one state twice.** A status dot inside a button, sitting next to an already colour-coded status badge, is redundant — keep the badge and drop the dot.
- **No help text or hover hints on form fields.** A well-named label is the explanation. Removed in two passes: first the visible hint lines under the inputs, then the tooltips I replaced them with.
- **No explanatory blurbs on cards** ("Re-pulls show & movie metadata (episodes, air dates, status) from TMDB/TVDB").
- **Prefer a conventional icon over a text button** where one exists — an eye to reveal a secret, not a "Show" link.

**Why:** the owner is the only user and already knows what the app does. Prose and duplicated indicators cost scanning effort without adding information, and they pad every control with vertical space.

**How to apply:** ship the label and the control; add explanation only if asked. Never encode *state* in placeholder text — grey bullets in a token field read as an example value, not as "a secret is stored" (use a badge for state, and keep placeholders for examples/instructions). When a hint feels necessary, that is usually a sign the label is wrong. Related: [[feedback_sentence_case_ui]], [[feedback_no_underline_links]], [[feedback_about_what_not_how]].

Not durable, and deliberately excluded from this memory: hiding vs. greying an unavailable section, and label-beside-field vs. label-above — both were situational choices for that one screen.
