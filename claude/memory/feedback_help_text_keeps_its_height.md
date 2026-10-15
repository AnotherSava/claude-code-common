---
name: feedback_help_text_keeps_its_height
description: A toggle's help text stays the same text and height in both states, and a dialog that resizes keeps its top-left corner fixed
metadata:
  type: feedback
---

Help text beside a checkbox or toggle stays the same text, at the same height, whichever state the
control is in. Don't swap in a shorter "what happens now" sentence when it is ticked, and don't hide
it. Text that has to change with the state goes elsewhere, below the control or on a later page,
where a change in its height moves nothing the user is looking at.

When a dialog has to change size between pages or states, keep its top-left corner where it is and
grow down and right. Move it up only when its bottom would otherwise leave the screen. On first
open, place it a little above the vertical middle of the screen the pointer is on, so it has room to
grow.

**Why:** in the achievement-overlay Add game wizard (2026-10-14), ticking "Replace it with GBE"
changed and then removed the description above it. The layout jumped, and the explanation the user
needed while deciding disappeared at the moment of deciding. A centred dialog that resized also
moved all four edges at once.

**How to apply:** when wording depends on a control's state, write one description that covers both
states. When a window's size depends on content, set a manual start position and anchor the
top-left on later resizes. Related: [[feedback_minimal_ui_chrome]].
