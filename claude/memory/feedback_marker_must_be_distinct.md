---
name: feedback_marker_must_be_distinct
description: A visual marker means something only by being unlike the others; reusing one for a second meaning is collision, not consistency
metadata:
  type: feedback
---

A visual marker — an accent bar, a badge, a colour, a glyph — carries meaning only by being **unlike**
the other marks on screen. Reusing an existing marker for a second meaning is not consistency; it is
collision, and it costs the original marker its meaning too.

**Why:** "reuse the idiom rather than invent one" is correct for *styles* (a card, a title, a
description) and backwards for *markers*. A style should look like its siblings. A marker exists to
be told apart from them.

**How to apply:** before reusing a mark, ask what else on screen already wears it, and whether the
two can be visible at once. If they can, change the **shape**, not just the position — colour alone
is not enough, and a second thing in the accent colour reads as the same thing. Give a notice its own
tint rather than borrowing a state colour (a selected-row background on a banner reads as another
selected row).

Real case: a diagnostic window's notice bar reused the nav rail's 3px accent marker, and sat directly
above that rail. Two identical bars a few pixels apart meant "this row is selected" and "this is
important". Fixed with a filled badge (a circle with a glyph) against the rail's thin bar, plus a
dedicated notice background instead of the selected-row grey.

Related: [[feedback_minimal_ui_chrome]], [[feedback_compound_label_hierarchy]].
