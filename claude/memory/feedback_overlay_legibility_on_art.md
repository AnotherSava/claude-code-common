---
name: feedback_overlay_legibility_on_art
description: An affordance overlaid on unpredictable imagery needs a flat dark scrim + solid mark, not a spotlight/translucent mark
metadata:
  type: feedback
---

When overlaying an affordance (play button, icon, label) on **unpredictable imagery** — posters, thumbnails, user photos — its legibility must not depend on the artwork underneath. Use a **flat, even dark scrim** (e.g. `black/50`) plus a **solid, opaque mark** (a solid-white glyph).

**Why:** contrast has to hold on light, dark, and busy/mixed art alike. A radial "spotlight" gradient that *brightens* the center, paired with a thin or translucent mark, fails exactly where the art is light or high-contrast. Concrete case: v1 of the poster "play" overlay used a center-brightening spotlight + a 94%-white thin triangle → it vanished on light posters; v2's flat even dim + a solid white triangle reads on every poster.

**How to apply:** for hover/press overlays on media art, reach for `bg-black/40–60` (flat) + a solid mark, and size the mark generously; skip decorative gradients whose readability rides on the underlying pixels. Pairs with [[feedback_understated_affordances]] (restraint) — this one is specifically about *guaranteed contrast over arbitrary backgrounds*.
