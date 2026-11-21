---
name: feedback_inline_edit_reads_as_value
description: A one-line field editing a value on a read page looks like the value at rest — aligned, border on hover/focus — and saves on blur, with no OK button
metadata:
  type: feedback
---

A field that edits a value in place on a page people read looks like the value at rest: its border and padding are pulled back so the text starts in the value column, the box appears only on hover and focus, and it saves itself: on blur and on Enter, with Escape putting the stored value back, and no OK button and no "save changes?" prompt. A field whose edit spans several inputs (a place with its street, a pair of days) saves when focus leaves the whole group. The save is confirmed on the field itself, its border turning green for a moment with a screen-reader "Saved", never by a note beside it that moves its neighbours.

**Why:** on 2026-11-01 a full-box name field on the trips booking page's From/To rows was called "quite messy" beside the three bordered buttons of the merge question under it; the borderless-at-rest version was approved. On 2026-11-20 the user found the trip page's Done tick misleading, because leaving edit mode dropped a name typed without pressing OK, and asked for research on asking at each blur. Shown that Atlassian's inline edit saves a one-line field on blur and that Nielsen Norman Group warns confirmation dialogs get clicked through when overused, they chose save on blur; a "Saved" note that shifted the controls after it was then replaced by the border flash at their request.

**How to apply:** one-line value fields on read pages. Multi-line editors (the extras text areas) keep their boxes. Related: [[feedback_minimal_ui_chrome]].
