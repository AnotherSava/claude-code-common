---
name: feedback_compound_label_hierarchy
description: Parts of a compound label get their own colour and weight — never one uniform run
metadata:
  type: feedback
---

A label that concatenates different kinds of information — a show + episode coordinates + episode name, a filename + size + status — sets each part in its own colour and weight rather than rendering as one uniform run. Step both down together: a full-strength weight in a paler grey reads as dimmed emphasis rather than as something quieter.

**Why:** run together in one colour and one face, the parts are a single grey stretch that has to be read word by word before it comes apart; given a weight each they separate at a glance. Feedback on a player bar that named an episode as one flat string: it "doesn't read well with all the items same colour, same formatting".

**How to apply:** rank the parts by what was chosen versus what merely locates it — the chosen thing leads, the coordinates recede furthest. Spacing does the same job and is worth tuning deliberately: equal gaps between the parts, and any separator *inside* a part (the dot in "S1 · E10") set tighter than those gaps, so the part doesn't come apart into two. Colouring parts separately means the label can't be a pre-joined string — give it a structure and one function that flattens it for aria-labels and tooltips, and render the gap as the same character the flat form uses rather than a CSS margin, so the two can't drift. See [[feedback_minimal_ui_chrome]] and [[feedback_no_underline_links]].
