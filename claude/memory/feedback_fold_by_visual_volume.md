---
name: fold-by-visual-volume
description: When folding/truncating display text, budget by lines AND characters; put the expand control on its own line
metadata:
  type: feedback
---

When collapsing/truncating long content for display, measure "too long" by visual volume — both line count AND the character length of individual lines — not line count alone.

**Why:** In the claude-code-dashboard history window I first implemented line-count-only folding. It missed two cases: entries with *few but very long lines* (a single ~2400-char line wraps into many visual rows) still overflowed, and the `<...>` expand button rendered glued to the end of the last visible line instead of on its own line.

**How to apply:** For any collapse/truncation UI, budget each end by *both* a max-lines and a max-chars limit, and add a character-truncation fallback for a single over-long line. Render the expand affordance as its own line. Relates to [[feedback_store_raw_derive_display]] (truncate at display time, not storage).
