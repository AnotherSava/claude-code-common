---
name: feedback_chart_neighbour_contrast
description: For categorical charts, prioritize adjacent-segment contrast over even hue spreading; colour by sorted position
metadata:
  type: feedback
---

For categorical charts (pie/donut/stacked/segmented), prioritize **adjacent-segment contrast over even hue spreading**, and assign colour by the segment's **sorted position** (so neighbours always differ) rather than by a fixed per-category hue.

**Why:** reviewing the import-performance pie (2026-06-29), the user said neighbour contrast is "even more important than spreading." Two segments that touch must look clearly different; an evenly-spread palette can still place two similar hues side by side once the data is sorted.

**How to apply:** order the palette as a sequence whose consecutive entries hop across the wheel (warm↔cool / complementary), then index into it by the slice's sorted rank — not by which category it is. Accept that the same category may get different colours across two charts (each chart has its own adjacent legend, so it stays readable). Only fall back to stable per-category colours if cross-chart colour matching is explicitly needed, at the cost of weaker neighbour contrast.
