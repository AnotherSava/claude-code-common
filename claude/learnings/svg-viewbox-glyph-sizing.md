# Sizing an inline SVG glyph — CSS width sizes the viewBox, not the path

A CSS width (Tailwind `w-[30%]`, `w-4`, `width: 2rem`, …) on an inline `<svg>` sizes the **viewBox canvas**, not the shape drawn inside it. If the `<path>` doesn't fill its viewBox — i.e. there's blank margin between the path's bounding box and the viewBox edges — the **visible glyph is smaller** than the CSS width implies, by exactly the padding ratio.

## The trap (real case)

A "play" triangle:

```html
<svg viewBox="0 0 24 24"><path d="M19 12 8.5 18.06 8.5 5.94Z" /></svg>
```

Its vertices are `(19,12) (8.5,18.06) (8.5,5.94)`, so the triangle's bounding box is x∈[8.5,19] (width 10.5), y∈[5.94,18.06] (height 12.12) inside a 24×24 box. The triangle therefore fills only **10.5/24 ≈ 44%** of the canvas width. Render it at `w-[30%]` of a poster and the *visible* triangle is `30% × 0.44 ≈ 13%` of the poster — less than half the size you'd assume from the `30%`. A design spec that says "≈30% of the poster width" while coding `w-[30%]` on this svg is wrong for exactly this reason.

## Fix: tighten the viewBox to the path's bounding box

Set the viewBox to the path's bbox (`min-x min-y width height`):

```html
<svg viewBox="8.5 5.94 10.5 12.12"><path d="M19 12 8.5 18.06 8.5 5.94Z" /></svg>
```

Now the path fills the canvas, so a CSS width maps **directly** to the glyph: `w-[30%]` = a triangle 30% of the poster's width. The `w-[…]` knob becomes intuitive (30% means 30%).

Two side effects, both usually improvements:

- **Optical centering for free.** With `0 0 24 24` the triangle had unequal margins (8.5 left vs 5 right), so centering the *canvas* left the *mark* offset right ("right-weighted"). A tight viewBox makes the canvas == the bbox, so centering the element centers the mark — no `margin`/`translate` nudge needed.
- **Aspect ratio follows the viewBox.** An `<svg>` with only `width` set (height `auto`) takes its height from the viewBox ratio. A tight, non-square viewBox (10.5:12.12 here) makes the element non-square — fine when it's centered in a flex box, but don't also force a square `w-N h-N` or you'll distort it (set width only, or match the ratio).

## Rule of thumb

If you want a CSS dimension on an inline SVG to mean "the glyph is this big," author the viewBox tight to the artwork. Reserve padded viewBoxes (like the ubiquitous `0 0 24 24` icon grid) for icon *sets* that must share one alignment box — and then remember the visible mark is smaller than the box, and size accordingly.
