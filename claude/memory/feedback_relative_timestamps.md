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

**A generated artifact has no second render, so the interval has to recompute itself.** The rule above assumes a page that renders again; a static HTML file written to disk does not, so an interval baked in at write time is simply wrong from the next minute onward — a report reading "scanned 8m ago" still reads it tomorrow. Asked about exactly that on 2026-09-14: *"'scanned 8 mins ago' is not correct - can it show interval dynamically instead?"*

- Embed the epoch on the element (`data-ts`) and compute the text in the page: on load, on a ~30s interval, and on `visibilitychange`. That last one is not optional — a backgrounded tab throttles timers hard, so a page returned to after hours shows whatever it last managed to render.
- Write the server-side value too, as the no-JS fallback, and render both through the **same** ported `formatInterval` so the two cannot disagree at a boundary.
- The same trap in the other direction: a value printed **once** to a terminal is a snapshot by nature and is correctly frozen. Don't add machinery there.
