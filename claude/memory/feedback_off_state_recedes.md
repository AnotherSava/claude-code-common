---
name: feedback_off_state_recedes
description: Parallel controls are one species; a toggle's ON state matches its always-on sibling and OFF is what recedes — never colour or strike-through
metadata:
  type: feedback
---

In a row of parallel controls, all of them are the same species. A plain text label beside a bordered button reads as two different kinds of thing even when they do the same job ("Audio" as a word next to "CC" as a button). Name each with the word the rest of the app already uses, not a domain abbreviation — "Subtitles", not "CC".

For a control that toggles, the ACTIVE state is the plain one: identical to a sibling label that is always active, because it means the same thing there. It is the INACTIVE state that deviates, and it does so by receding — the label and the control it governs together, at reduced opacity.

Two things not to reach for:

- **Colour.** On an otherwise greyscale surface, a lone accent-tinted element is the only coloured thing on screen and reads as decoration rather than state.
- **Strike-through.** A line through a word at UI sizes destroys its legibility, and costs more than the state is worth.

**Why:** the user rejected each in turn while the player bar was being built — the bordered CC badge for not matching "Audio" beside it, the accent pill for being the only blue in the UI, the struck-out label for being unreadable, and an off state that looked identical to an always-on sibling for being indistinguishable from working.

**How to apply:** style the active state first, by copying whatever static label sits beside it; then find the off state by taking light away from the whole group. Related: [[feedback_minimal_ui_chrome]], [[feedback_no_underline_links]].
