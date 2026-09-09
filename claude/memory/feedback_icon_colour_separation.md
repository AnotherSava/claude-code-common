---
name: feedback_icon_colour_separation
description: Adjacent steps of a small coloured scale separate on hue, not shade, in the direction away from the opposite pole — and the separation is checked at final size
metadata:
  type: feedback
---

Two colours a step apart on the same hue read as one colour at icon size. A five-step opinion scale
drawn at 15px used `#44cc44` and `#88bb44` for its two willing steps and they were indistinguishable;
corrected 2026-09-07 with "both greens look too similar".

**Why:** at that size a hairline stroke leaves very few coloured pixels, and a shade difference needs
area to register. Two further traps came out of the same exchange. Separating *toward yellow* moved
the willing step toward the unwilling end of the ramp it sits at the head of, so the scale read as two
warm steps either side of neutral — the direction has to move **away** from the opposite pole (green
to cyan, not green to olive). And thin strokes have to be thickened before any hue change helps,
because otherwise there is not enough coloured pixel to carry it.

**How to apply:**
- **Render candidates, never pick from hex.** Three or four variants through the real renderer at the
  real size, compared side by side. Magnify afterwards to confirm the shapes still read, but judge
  the colour at 1:1, since that is where it has to work.
- **Check the new colour against its neighbour in the ramp**, not only against the one it is being
  separated from. Lightening cyan toward white on request, past roughly 55% it started reading as a
  pale thing next to the neutral grey beside it.
- **Name the cost.** Matched luminance is what makes a ramp feel even; the original green and cyan
  were both 160. Lightening one step to 189 broke that evenness. That is a real trade and belongs in
  the reply rather than being quietly absorbed.
- **Shape keeps carrying the meaning.** The mouth curvature distinguishes the steps on its own, so
  colour only reinforces it — the same standard as
  [[feedback_redrawn_icons_keep_identity]] and the colour-blind-safe suit shapes it sits beside.

Shares the "neighbours must differ" principle with [[feedback_chart_neighbour_contrast]], and stops
there: that one is about *assigning* colours to chart segments by sorted position so touching slices
differ. This one is about an ordinal scale whose order is fixed and whose steps are too small to
carry a shade difference at all.
