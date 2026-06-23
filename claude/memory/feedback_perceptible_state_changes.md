---
name: feedback_perceptible_state_changes
description: A hover/state change reported as "barely noticeable" needs a distinct shade swap, not a nudged filter — a ~6% brightness shift on a saturated fill reads as no change
metadata:
  type: feedback
---

When the user says a hover/active state change is "barely noticeable," don't keep nudging the existing subtle effect — replace it with a distinct, clearly perceptible change.

**Why:** A primary button's hover was `filter: brightness(1.06)` (~6% lift) on a mid-dark saturated blue — imperceptible. The user flagged it twice; even a small darken still read as weak. The fix was a clearly darker token (oklch lightness 0.525 → 0.40) swapped as the background, plus a lift shadow and a 1px `translateY`.

**How to apply:** For hover/active feedback prefer a real background/colour **token swap to a markedly different shade** over `brightness`/`opacity` filters (a small multiplier on a saturated colour is invisible). Reinforce with a shadow/transform when in doubt. Verify visually (drive the browser) rather than guessing magnitudes — and a filter-only `:hover` with no `background` is also fragile to cascade overrides. Relates to [[feedback_default_cursor_noninteractive]] (interaction affordances must be honest/visible).
