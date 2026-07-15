---
name: feedback_match_visual_by_tracing
description: Reproduce an icon/logo/reference image by pixel-overlay tracing + iteration, not from memory
metadata:
  type: feedback
---

When asked to reproduce a visual — an icon, logo, glyph, or screenshot crop — "exactly", "the same", or so it "pixel-matches", trace the actual image and iterate with an **overlay comparison** until it matches. Do not redraw it from interpretation or memory.

**Why:** redrawing a BambuStudio "auto orient" icon from memory got the arrow direction, stroke weight, and proportions wrong across several attempts; the user pushed *"why don't you keep comparing pixels with the original"*. Guessing from a description is faster per attempt but converges slowly and frustrates.

**How to apply:** see [[icon-tracing-pixel-overlay]] — upscale + grid the reference, author paths in its native pixel coordinate space, composite your render (semi-transparent) over the faded target, measure stroke width from the dark-core pixels rather than eyeballing, and parametrize constrained shapes (a true square as center/half-side/rotation) so tweaks preserve invariants. Related: [[feedback_verify_gui_via_repro]] (build a repro/mock to verify what you can't screenshot).
