# Tracing an icon/glyph from a reference image into SVG

When asked to reproduce an icon, logo, or glyph from a reference image (a screenshot,
a toolbar-button crop) "exactly" or "so they pixel-match", **do not redraw it from
memory or from a verbal description**. Redrawing from interpretation reliably gets
details wrong — arrow direction, stroke weight, corner angles, proportions — and each
"try again" burns a round-trip. Trace the actual pixels and iterate with an overlay.

This is the method that converged after several failed from-memory attempts on a
BambuStudio "auto orient" toolbar icon (a tilted plate + curved arrow + bed bar + "AUTO"
label) rebuilt as a stroked SVG for a web app's icon set.

## The loop

1. **Upscale the reference with a coordinate grid.** The source is often tiny (e.g.
   75×70 px). Upscale ~10–18× (`kernel: "nearest"` to read exact pixels; `"cubic"` to
   read shape) and overlay a grid labelled in the *original* pixel coordinates. Read
   corner/endpoint coordinates straight off the grid. Crop-and-zoom sub-regions (an
   arrowhead, a curve) for detail.

2. **Design paths in the reference's NATIVE pixel space**, not the target `viewBox`.
   If the reference is 75×70, author the SVG in a `0 0 75 70` viewBox. This makes the
   overlay 1:1 — no mental scaling while comparing.

3. **Overlay-compare every iteration.** Render your SVG at the reference size, fade the
   target to ~50% grey, composite your strokes in **semi-transparent red** over it, and
   also lay out `target | mine | overlay` side by side. Deviations jump out (red
   spilling past grey = too big/thick/misplaced). Adjust coordinates, re-render, repeat.

4. **Measure, don't eyeball, the stroke width.** Read the raw greyscale and count the
   dark-core run-length across a stroke (e.g. the bed's top edge, the plate's edge). A
   3-px-looking line is often a ~1.5-px core plus anti-aliasing. Match that.

5. **Parametrize constrained shapes so tweaks preserve the invariant.** "Make it an
   actual square (90° corners)" is impossible to keep by nudging four independent
   corners. Define the square by `{center, halfSide, rotation}` and *compute* the
   corners — then you can slide/rotate/resize it and it stays a true square. Same idea
   for regular polygons, concentric rings, etc.

6. **Curves: trace 3–4 centreline points, then fit a Bézier.** A "curved arrow" that
   reads as a straight diagonal usually means the endpoints are right but the control
   point is weak, or the start point sits in the wrong place. Where a shaft meets an
   arrowhead, land it on the **midpoint of the arrowhead's back edge**, not a corner and
   not inside the triangle.

## Embedding into a fixed-viewBox icon set

The app's `<Icon>` almost always hard-codes one `viewBox` (e.g. `0 0 24 24`) and one
`stroke-width`. Keep the traced paths in their native space and fit them with a wrapper
transform instead of re-authoring coordinates:

```jsx
// content bbox [13,11]–[64,58] in 75-space → fit into ~[1,23] of the 24 box
<g transform="translate(-4.603 -3.107) scale(0.431)" strokeWidth={1.4}>
  <path d="…75-space coords…" />
  <rect … strokeWidth={1.3} />           {/* per-element stroke overrides survive */}
  <text x="13" y="27" fontSize="10" textLength="18" lengthAdjust="spacingAndGlyphs"
        fill="currentColor" stroke="none">AUTO</text>
</g>
```

- `stroke-width` set on the `<g>` is in the *child* (75-space) units and is scaled by the
  transform — so a `strokeWidth={1.4}` here renders `1.4 × 0.431 ≈ 0.6` in the 24-box.
  Keeping the target's stroke-to-content *ratio* means it looks like the reference at any
  render size.
- A `<text>` label locks its width with `textLength` + `lengthAdjust="spacingAndGlyphs"`
  (so a system font's glyph metrics can't blow out the width) and sets `fill="currentColor"
  stroke="none"` (the parent `<svg fill="none" stroke="currentColor">` would otherwise make
  outlined, invisible text). A small text label is font-substitution-fragile — offer to
  outline it to paths if pixel-stability matters.

## sharp snippets (Node, ESM)

Grid overlay on the upscaled reference:

```js
import sharp from "sharp";
const S = 12, W = 75, H = 70;                     // scale, original dims
const base = await sharp(src).flatten({ background: "#fff" })
  .resize(W*S, H*S, { kernel: "cubic" }).toBuffer();
let g = "";
for (let x = 0; x <= W; x += 5) { const X = x*S, b = x % 10 === 0;
  g += `<line x1="${X}" y1="0" x2="${X}" y2="${H*S}" stroke="${b?'#e00':'#fbb'}" stroke-width="${b?1.5:.6}"/>`;
  if (b) g += `<text x="${X+2}" y="14" font-size="13" fill="#e00">${x}</text>`; }
// …same for rows…
await sharp(base).composite([{ input: Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W*S}" height="${H*S}">${g}</svg>`) }]).png().toFile(out);
```

`target | mine | overlay` comparison:

```js
const mine   = Buffer.from(`<svg … viewBox="0 0 ${W} ${H}">${glyph("#e00")}</svg>`);   // your paths
const target = await sharp(src).flatten({ background:"#fff" }).resize(W*S,H*S,{kernel:"cubic"}).toBuffer();
const faded  = await sharp(target).linear(0.5, 255*0.5).toBuffer();                     // grey it down
const overlay = await sharp(faded).composite([{ input: await sharp(mine).ensureAlpha(0.85).toBuffer() }]).toBuffer();
// then composite target / mine-on-white / overlay into one strip and view it
```

Run these as a throwaway `.mjs` inside the app dir (so `sharp` resolves from its
`node_modules`), write the PNG to the OS temp dir, view it, and delete the script when
done. `sharp` uses librsvg/resvg; if it renders your SVG correctly, the browser will too.

## Verifying a CSS treatment you can't screenshot

When the change is a CSS layout you can't easily screenshot (e.g. a corner button
clipped by a rounded, `overflow:hidden` card), mock it in an SVG with a `clipPath`
standing in for the overflow clip and render it with sharp — enough to confirm the corner
radii and flush edges before shipping.
