---
name: feedback_understated_affordances
description: Prefer restrained UI affordances — small neutral icon over a bold colored pill; brand color only on hover/active
metadata:
  type: feedback
---

When adding a clickable indicator or action affordance (e.g. a "watch in Plex" control on cards/headers), favor a **small, neutral icon** over a bold colored pill-with-label. Keep the **resting state neutral/muted** and reserve the **saturated brand color for hover/active** — not the default.

**Why:** The user repeatedly tones affordances down toward low-chrome. On the Plex play button they went: filled gold "▶ Plex" pill → "don't show the yellow pill everywhere, use a play icon" → bare triangle ("looks weird, add a background") → circular chip → "make it less golden" → landing on a neutral gray chip + muted triangle that only reveals Plex gold on hover. Same pattern as [[feedback_sentence_case_ui]] (low-key labels) and [[feedback_default_cursor_noninteractive]].

**How to apply:** Default an icon affordance to `text-[var(--color-muted)]` on a subtle surface chip; put the brand/accent color behind `hover:`/active only. Make the hover a distinct shade/token swap so it's perceptible ([[feedback_perceptible_state_changes]]), not a brightness nudge. When the visual weight is genuinely uncertain, render a couple of options at target size and let the user pick ([[feedback_offer_visual_options]]) rather than iterating one nudge at a time.
