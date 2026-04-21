# CSS Layout Gotchas

Non-obvious behaviors that bit me when building dashboard-style UIs with mixed grid/flex layouts. All verified in Chromium-based engines (Electron, Chrome). Safari should behave the same but not always verified.

## `grid-row: 1 / -1` doesn't span implicit rows

The `-1` in `grid-row` / `grid-column` counts from the **last line of the EXPLICIT grid** — meaning the lines defined by `grid-template-rows` / `grid-template-columns`. If you don't declare those properties, the explicit grid has 0 tracks in that axis, so `-1` resolves to line 1 and the span collapses to nothing useful.

**Bug case:**

```css
.grid {
  display: grid;
  grid-template-columns: 1fr auto;
  /* no grid-template-rows declared */
}
.spanner {
  grid-column: 2;
  grid-row: 1 / -1;  /* BROKEN — spans row 1 only */
}
```

Items referencing implicit rows (`grid-row: 2` etc.) DO create those rows, but those implicit rows don't count toward `-1` resolution.

**Fix: use `span N` instead.** `span` works in implicit-row grids:

```css
.spanner {
  grid-column: 2;
  grid-row: 1 / span 2;  /* creates an implicit row 2 if needed */
}
```

Combined with `align-self: center`, this gives you the "item centered vertically across two rows" pattern — useful for state clusters on multi-row list items.

## `overflow: hidden` clips at the padding-edge, not the content-edge

The CSS Overflow Module defines the overflow clipping edge as the **padding-box**, not the content-box. This means padding space is *inside* the clip region and content rendered into padding stays visible.

**Use case: descender clearance with tight line-height.**

With `line-height: 1`, the line-box is exactly the font-size tall. Descenders (`g`, `y`, `p`, `j`) extend below the line-box and `overflow: hidden` at the content-edge would clip them. But because clipping happens at the padding-edge, `padding-bottom` gives descenders a visible region:

```css
.chat-name {
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-bottom: 3px;   /* descenders live here, visible */
  margin-bottom: -3px;   /* pulls subsequent layout back up */
}
```

The negative margin-bottom compensates so the element's effective layout height stays the content-box size — neighbors aren't shifted by the padding.

This lets you get pixel-tight vertical alignment with `line-height: 1` WITHOUT chopping descenders.

## `canvas.measureText()` is the reliable "natural text width"

`element.scrollWidth` lies in a specific case that bites grid/flex "would this fit?" decisions:

- Content **longer** than the element's inner width → `scrollWidth` returns the content's natural width. ✓
- Content **shorter** than the element's inner width → `scrollWidth` returns `clientWidth` (the element's own width). ✗

A short label rendered in a 300px-wide cell reports `scrollWidth === 300` even if the text itself would only take 25px at natural size. Breaks any "measure this and see if it fits somewhere else" logic.

**Fix: use a canvas context to measure text independent of the DOM.**

```js
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');
ctx.font = "9px 'Segoe UI', system-ui, sans-serif";  // must match the target CSS font
ctx.measureText('hello world').width;  // real natural width in pixels
```

Caveats:

- The `font` string must match the element's computed font (`font-style font-variant font-weight font-size/line-height font-family` — the CSS `font` shorthand order). Any mismatch yields a different width.
- Synchronous and cheap (sub-millisecond for typical labels). Safe to call per-render for a handful of elements.
- **Don't use character count as a proxy.** Proportional fonts vary hugely — "mmmm" vs "iiii" can differ 3×.
- If the decision depends on container width (e.g. "fits inline if label + siblings ≤ container"), re-run on `window.addEventListener('resize', adjust)`.

**Pattern**: computing "does X fit inline alongside Y and Z?":

```js
const available = container.clientWidth
                  - paddingL - paddingR
                  - siblingsTotalWidth
                  - gaps;
const labelWidth = ctx.measureText(text).width;
const fits = labelWidth <= available;
```

## CSS Grid `1fr` + `gap` rounds per track, producing uneven widths

`grid-template-columns: repeat(N, 1fr)` with `gap: 1px` tells the browser to distribute `(W - (N-1)px)` across N equal tracks. If that doesn't divide evenly (most of the time), the browser rounds each track independently — some `floor`, some `ceil`. Visible result: tracks with consistently 1 px gaps but inconsistently-sized colored widths.

Using explicit `calc()` as the track template — `repeat(N, calc((100% - (N-1)px) / N))` — doesn't help. Same per-track rounding, same uneven output. Flex with `flex: 1 1 0` on each child also rounds per-child.

**Fix for segmented bars:** render a single `repeating-linear-gradient` on one element rather than N grid/flex children. The gradient paints at sub-pixel precision from one definition, so all tiles are byte-identical. See `~/.claude/memory/feedback_pixel_precise_css_segments.md` for the formula.

**When to accept the rounding:** if segments are wide (≥ 20 px) and the visual is dense enough that per-track ±1 px is imperceptible, `1fr` is fine. Thin segments (< 10 px) make the unevenness obvious.

## `min-width` includes padding under `box-sizing: border-box`

With `box-sizing: border-box` (set globally in most modern apps), `min-width` sets the *border-box* floor, not the content-box. If the element has horizontal padding, `min-width: 4ch` gives `4ch` of total border-box width and only `4ch - 2*padding` of content area — not enough to hold 4 monospace characters of text.

**Symptom:** caps/labels with a `min-width` in `ch` units appear to "ignore" their floor whenever their text grows past `min-width - 2*padding`, because content overflows the padded content area and expands the border box past the floor. Two elements with the same `min-width` but different text lengths end up different widths.

**Fix:** include the horizontal padding in the min-width, e.g. `min-width: calc(4ch + 10px)` for an element with `padding: 0 5px`. Or scope `box-sizing: content-box` to just that element if you want `min-width` to mean "content area min".
