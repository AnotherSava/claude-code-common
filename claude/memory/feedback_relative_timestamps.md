---
name: feedback_relative_timestamps
description: Past timestamps render as a compact relative interval with the exact stamp on hover; port formatInterval from the What's Next repo rather than writing another one
metadata:
  type: feedback
---

A past timestamp in a UI reads as a relative interval — "3h ago", "12d ago" — with the exact stamp on the same element's `title` for hover. Asked for this on a change log showing `20 Aug 22:13`, the owner pointed at the What's Next repo as where it had already been specified in detail, rather than describing it again.

The house implementation is `formatInterval` in that repo's `web/src/lib/format.ts`. Port it; do not write a fresh one, or the apps drift into different unit sets and a reader has to learn the vocabulary twice. Its rules:

- Largest unit only, floored: `m` / `h` / `d` / `mo` / `y`. A month is 30 days, a year 365.
- Clamped to `1m` — nothing ever reads `0m`, and a negative interval (a clock a few seconds out of step) reads `1m` rather than something absurd.
- Months are `mo`, never a capital `M`: a column where minutes and months differ only by one letter's case gets misread.
- It returns bare magnitude. The caller appends "ago" or "left".

**Why:** the interval is what a reader actually wants from a past event, and the exact instant is wanted rarely enough that hover is the right place for it — which also frees the visible column to be narrow.

**How to apply:** relative in the text, absolute in `title`, on the same span. Read the clock **once per page**, not per row, or two rows written by the same event disagree about how long ago it happened. In a Next 16 render body that clock read trips `react-hooks/purity` — use a `nowMs()` wrapper in a lib module rather than a per-call-site disable (see the `nextjs-react-hooks-purity` learning). Related: [[feedback_minimal_ui_chrome]].
