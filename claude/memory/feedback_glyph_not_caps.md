---
name: feedback_glyph_not_caps
description: Emphasis inside small muted text needs a glyph that carries its own colour — capitals inside grey text still read grey
metadata:
  type: feedback
---

A line that has to be noticed cannot be made noticeable by wording when it renders as small muted text. Capitals
do not rescue it: "3 sign-up(s) NOT confirmed" set in `text-muted` is still grey, and grey is what the eye skips
over. The user's words for it — "gray text doesn't catch an eye, even when all caps".

**Use a glyph that brings its own colour** (⚠️ for something to act on, ✅ for something settled), and drop the
capitals once it is there — the icon does that job, and shouting alongside it is just noise.

**Why an emoji rather than a styled span.** It keeps its colour inside muted text without fighting the
surrounding class, and it survives being stored in a plain-text column and quoted into another view — so one
change reaches every surface the string reaches. A CSS class only styles the one component that knows about it.
Reach for a styled element instead when the text never leaves a single component.

Only the line worth acting on gets the glyph. Marking the calm case too spends the signal that makes the other
one findable — an all-confirmed message stays plain.

**First look for something already there to recolour.** A glyph is the answer for a line of prose, which has no
other element to carry a state. Where the layout already holds one that means something adjacent, colour *that*
instead of setting a mark beside it. Real case: a 🎫 sat next to a seat-count pill on a calendar block, competing
for width in the one line that had any to spare, for a fact the pill was in a position to say for free — green
fill for "your place is confirmed", amber for "not confirmed at the source". The glyph came out and nothing was
lost. The ⚠️ in the muted prose line above it stayed, because there was nothing there to recolour.

Related: [[feedback_status_colour_vs_page]] (a fill must clear its contrast against the page, not just its own
ink), [[feedback_minimal_ui_chrome]] (icon over text button, state in a badge),
[[feedback_compound_label_hierarchy]] (weight and colour per part of a label).
