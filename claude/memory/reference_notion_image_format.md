---
name: Notion image format choice — WebP, not AVIF
description: For images bound for Notion, default to WebP because Notion does not preview AVIF in card/gallery views
type: reference
---

When uploading optimized images to Notion (file properties, body image blocks, page covers), use **WebP** by default — typically q=60, max-width 1024 — not AVIF.

**Why:** AVIF gives ~25-30% smaller files at equivalent quality, but Notion's gallery/card thumbnail renderer does not preview AVIF. The image is stored fine and downloads correctly, but the card just shows no thumbnail. WebP renders fine. Confirmed May 2026, when two Notion databases were first populated with AVIF images and had to be redone as WebP.

For typical phone photos (~1-3 MB JPGs), WebP at q=60 + 1024-wide gives ~10-15% of original size. For already-small inputs (<200 KB), the ratio is closer to 35-40% — diminishing returns.

**How to apply:**
- The toolbox `image-opt` tool defaults to WebP — leave that alone for any Notion-bound image. Encoder settings live in [[reference_toolbox_image_opt]].
- AVIF is still fine for non-Notion targets (GitHub, blogs, anything that can render it).
- If a future Notion release adds AVIF preview, retest before changing the default.
