---
name: Pixel-precise CSS segmented bars
description: CSS pattern for fixed-width segmented progress bars that auto-retile on resize with zero JS
type: feedback
---

For segmented progress bars that must stay pixel-precise across container widths, use a repeating linear-gradient:

```css
.track {
  background-image: linear-gradient(to right, #45454a 8px, transparent 8px);
  background-size: 9px 100%;   /* 8px segment + 1px gap = 9px pitch */
  background-repeat: repeat-x;
  overflow: hidden;
  border-radius: 3px;
}
.fill {
  position: absolute; top: 0; bottom: 0; left: 0;
  background-image: linear-gradient(to right, var(--fill-color) 8px, transparent 8px);
  background-size: 9px 100%;
  background-repeat: repeat-x;
}
```

Layer `.track` (empty color) with an overlaid `.fill` div (fill color) that shares the same pattern and starting point. Both patterns anchor to `left: 0`, so filled and empty segments align perfectly at the fill boundary.

**Why:** Zero JS for the repeat — browser auto-retiles on resize. No `{#each}` of N spans, no flex math. `overflow: hidden` + `border-radius` on `.track` clips the trailing partial segment cleanly. Performance: browser is already optimized for gradient tiling.

**How to apply:** any "LED-strip" / equalizer-style bar with fixed segment width. For all-or-nothing whole-segment fill (no partial segments at the boundary), add a `ResizeObserver` that snaps `.fill` width to `filledSegments * pitchPx`, otherwise set width by percent and let the gradient cut wherever. For stable segment width regardless of how many fit, use pixel values (not `fr`). If you need the segment count to inform logic (e.g. round utilization to nearest whole block), measure the track width in the observer callback and compute `floor(width / pitch)`.

## Variant: fixed count N, adaptive width (segments scale with track)

For "always N segments regardless of container width", use a tile size that accommodates the 1 px gap, so N tiles span exactly `W + 1 px` (trailing gap clipped):

```css
.segments {
  background-image: linear-gradient(
    to right,
    #45454a 0,
    #45454a calc(100% - 1px),
    transparent calc(100% - 1px)
  );
  background-size: calc((100% + 1px) / var(--n)) 100%;
  background-repeat: repeat-x;
  overflow: hidden;  /* clips the trailing 1px gap of the last tile */
}
.fill {
  position: absolute; top: 0; bottom: 0; left: 0;
  width: calc(var(--filled) * (100% + 1px) / var(--n) - 1px);
  background-image: linear-gradient(
    to right,
    var(--fill-color) 0,
    var(--fill-color) calc(100% - 1px),
    transparent calc(100% - 1px)
  );
  background-size: calc((100% + 1px) / var(--filled)) 100%;
  background-repeat: repeat-x;
}
```

**Math:** N tiles of width `(W+1)/N` sum to `W+1`; the trailing 1 px gap is clipped by `overflow: hidden`. Each tile paints `(tile - 1 px)` of color then 1 px transparent gap. The fill overlay's own tile size `(fillW + 1 px)/filled` reduces algebraically to the same `(W+1)/N`, so parent and fill patterns stay aligned pixel-for-pixel at every segment boundary.

**Set `--n` and `--filled` as inline styles** on the elements (or as props passed into the component). Percent inside CSS custom properties referenced in `calc()` works without `var(--n) * 1` tricks in modern browsers.

**Do NOT try CSS Grid `repeat(N, 1fr)` + `gap: 1px` as the alternative** — browsers round each track independently, producing visibly uneven colored widths even with identical 1 px gaps. `repeat(N, calc((100% - (N-1)px) / N))` doesn't help either; same per-track rounding. Only the single-element repeating-gradient gets consistent sub-pixel painting.
