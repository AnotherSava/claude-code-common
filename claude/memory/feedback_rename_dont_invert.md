---
name: feedback_rename_dont_invert
description: When a mechanism can only express one direction, rename the control to match it rather than wiring inverted semantics behind the label you first wanted
metadata:
  type: feedback
---

When a control's mechanism can only express one direction, name the control for what the mechanism does. Do not
keep the label you first had in mind and invert the wiring behind it.

The case that prompted it: an HTML checkbox only submits when ticked, so the absent parameter has to be the
default state. A filter that is **on by default** therefore cannot be a ticked "No blacklisted" — it becomes an
unticked "Blacklisted" that means *show them*. I proposed inverting the checkbox instead (styling the pill filled
when unchecked) to keep the requested wording; the user's answer was "feel free to rename it and use the opposite
meaning".

**Why:** the inverted version needs a paragraph of comment to explain why `checked` means "off", and every later
reader — including the next form field added beside it — has to hold that inversion in their head. Renaming costs
one word and leaves the label, the checkbox, the URL parameter and the stored field all saying the same thing.

**How to apply:** when a requested label fights the mechanism (checkbox-only-when-ticked, a radio group with no
"none", a toggle whose default is the non-expressible state), say so and propose the renamed version rather than
building the inversion quietly. The same goes for a param that would have to be `?thing=off`: name it for what it
turns on. Related: [[feedback_microcopy_user_facing_state]] — that one is about jargon versus plain state, this
one about wording versus mechanism.
