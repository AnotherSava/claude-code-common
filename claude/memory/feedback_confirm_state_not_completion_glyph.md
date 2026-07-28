---
name: feedback_confirm_state_not_completion_glyph
description: A two-step confirm's armed state must read as "action pending" (labeled CTA), not a completion glyph like ✓ that looks already-done
metadata:
  type: feedback
---

For a two-step confirm affordance (click to arm, click again to commit), the armed/intermediate state must clearly signal the action is STILL PENDING — a labeled call-to-action (e.g. a "＋ Add" pill) — never a completion glyph like a ✓/checkmark, which reads as "already done" and makes users think the action finished on the first click.

**Why:** On the What's Next search-page "+" add button, arming showed an accent checkmark; the user reported "it shows check mark right away and it's not clear at all that user needs to click one more time to add." A check is universally "complete", so it terminated the interaction in the user's mind. Replacing it with an expanded "＋ Add" pill (an obvious call-to-action) fixed it.

**How to apply:** Armed states are imperative/labeled CTAs or clearly-transient treatments (ring, fill, "Confirm?"), reserving ✓ for the actual completed state — and keep the completed state visually distinct from the armed one. Relates to [[feedback_understated_affordances]], [[feedback_perceptible_state_changes]], [[feedback_no_underline_links]].
