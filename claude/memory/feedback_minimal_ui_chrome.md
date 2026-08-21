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
- **A control whose own text names it takes no separate field label** (2026-08-08). I gave the playback radio a label column — "Playback ◉ Use this server" — where the control's own words were already the label. It became an unlabelled "Default playback" radio: the don't-signal-twice rule above, applied to naming rather than to state.
- **An element must answer a question THIS page is asking** (2026-08-09). Two of mine that didn't, both caught by the owner: a green "saved" tick on a form whose saves take ~25ms — confirming something already over, then persisting for the rest of the page's life (only slow and failed states earn a mark; instant success is silent), and a "+49 more" count on a shelf that means "playable right now", where the honest number was the 9 episodes actually downloaded. Neither was *duplicated* information, which is what let them survive review — they were irrelevant, or measured in the wrong currency. Ask what the page is for, then check that every number and mark on it is denominated in that.
- **An escape hatch belongs to the failure, not to the chrome** (2026-08-11). The in-app player carried a permanent "Open in Jellyfin" link in its bar; the owner had it removed, then asked for it back *when something didn't work*. A working play has no use for a way out, and a standing exit mid-film only invites losing your place — but the moment a play refuses to start, the other client is the most useful thing on screen. Same test as the bullet above: the element has to answer what THIS moment is asking, and "how do I escape" isn't a question a working player raises.
- **When explanation IS warranted, collapse it rather than inline it** (2026-08-07). Help for genuinely non-obvious syntax — a printf-style season format, a `{query}` placeholder — belongs behind a disclosure whose resting state is one line, not a paragraph re-read on every visit. Organize it as a term/definition list rather than prose, and make the toggle read as a control (soft-fill pill + chevron), never as more of the sentence beside it.

- **A list row's padding must not outweigh its content** (2026-08-20). Rows at `py-3` around a single line of text measured 53px, 24 of it padding; asked to make them "much more compact vertically" they came down to 33px — `py-1`, a 24px toggle rather than 28px, and the date moved inline with the time so every row is one line. Same instinct as the rest of this note: the chrome was costing more vertical space than the information it framed.

**Why:** the owner is the only user and already knows what the app does. Prose and duplicated indicators cost scanning effort without adding information, and they pad every control with vertical space.

**How to apply:** ship the label and the control; add explanation only if asked. Never encode *state* in placeholder text — grey bullets in a token field read as an example value, not as "a secret is stored" (use a badge for state, and keep placeholders for examples/instructions). When a hint feels necessary, that is usually a sign the label is wrong. Related: [[feedback_sentence_case_ui]], [[feedback_no_underline_links]], [[feedback_about_what_not_how]].

Not durable, and deliberately excluded from this memory: hiding vs. greying an unavailable section, and label-beside-field vs. label-above — both were situational choices for that one screen.
