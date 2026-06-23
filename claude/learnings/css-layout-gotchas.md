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

## `offsetHeight` rounds per element — summing across rows under-counts

`HTMLElement.offsetHeight` returns an integer (per spec, rounded). Summing the heights of N siblings to compute "what window size do I need to fit all this content" yields up to `N` pixels of under-count, because each child's fraction is rounded down. The OS resize honors what you asked for exactly, so a scrollbar appears even though "the math added up."

**Symptom:** auto-fit window logic that walks `.list.children` and sums `offsetHeight` ends up 3-6 px short on a 4-row list, with a scrollbar always present.

**Fix:** sum `getBoundingClientRect().height` (fractional) and ceil the total before requesting the resize:

```js
let listH = 0
for (const child of list.children) {
  listH += child.getBoundingClientRect().height
}
const desired = Math.ceil(headerEl.getBoundingClientRect().height + listH)
```

`offsetHeight` is fine when you only need approximate "is this big or small" — unsuitable for "exactly fit N items, no scrollbar."

## `min-width` includes padding under `box-sizing: border-box`

With `box-sizing: border-box` (set globally in most modern apps), `min-width` sets the *border-box* floor, not the content-box. If the element has horizontal padding, `min-width: 4ch` gives `4ch` of total border-box width and only `4ch - 2*padding` of content area — not enough to hold 4 monospace characters of text.

**Symptom:** caps/labels with a `min-width` in `ch` units appear to "ignore" their floor whenever their text grows past `min-width - 2*padding`, because content overflows the padded content area and expands the border box past the floor. Two elements with the same `min-width` but different text lengths end up different widths.

**Fix:** include the horizontal padding in the min-width, e.g. `min-width: calc(4ch + 10px)` for an element with `padding: 0 5px`. Or scope `box-sizing: content-box` to just that element if you want `min-width` to mean "content area min".

## Sibling grid-rows don't share column widths — use subgrid

If each "row" in your list is its own `display: grid` container, each row computes its column widths independently. `auto` and `1fr` resolve per row, so a right-flush "$30" cell in one row is a different width than the empty cell below it — the columns won't visually align.

**Bug case:** parent uses `display: table` (or any non-grid container), each row is a 4-column grid. Discount column and date column visually drift between rows.

**Fix:** move the grid template to the parent and have each row inherit via `subgrid`:

```css
.summary-list { display: grid; column-gap: 10px; }
.summary-list.deals { grid-template-columns: minmax(80px, 22%) 1fr auto auto; }
.summary-row {
  display: grid;
  grid-template-columns: subgrid;
  grid-column: 1 / -1;     /* the row spans all parent columns */
}
```

Now all rows participate in the parent's column track sizing — `auto` columns size to the widest content across all rows, and right-aligned cells stack vertically.

Requires Chrome 117+ / Firefox 125+ / Safari 16+. Note `gap` is inherited from the parent in a subgrid; setting `gap` on a subgrid row has no effect.

## Confine scroll to a child region — flex column + `min-height: 0`

To make only an inner region scroll (e.g. a long table) instead of the whole page, the scroll container must be height-bounded **and** the scrollable child must be allowed to shrink below its content size:

- The ancestor fills the viewport: `height: 100vh; overflow: hidden` (add `box-sizing: border-box` if it has padding, or the padding adds to `100vh` and overflows).
- That ancestor (or an intermediate wrapper) is `display: flex; flex-direction: column`.
- Non-scrolling siblings (header, toolbar, chart) keep their natural height.
- The scrollable child: `flex: 1; min-height: 0; overflow-y: auto`.

```css
body:has(.stats-page) { height: 100vh; overflow: hidden; box-sizing: border-box; }
body:has(.stats-page) #content { height: 100%; }
.stats-page { height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }
.stats-table-wrap { flex: 1; min-height: 0; overflow-y: auto; }   /* the only scroller */
```

The crucial, non-obvious part is **`min-height: 0`**. A flex item's default `min-height` is `auto`, which refuses to shrink below the content's intrinsic size — so without it the child grows to fit all its rows and the *page* (or next ancestor) scrolls instead of the child. `min-height: 0` lets it shrink, and its own scrollbar appears.

Scope it to one view inside a shared container with `:has()` (`body:has(.stats-page) { … }`) so sibling views in the same container keep normal document scrolling. `:has()` needs Chrome 105+.

To push the scrollable child (and its scrollbar) out to the container's edge past the ancestor's padding, give it a negative margin equal to that padding: `.stats-table-wrap { margin-right: -20px; }`.

## Sticky `thead th` + `border-collapse` drops the header border on scroll

A sticky table header — `thead th { position: sticky; top: 0 }` — needs an opaque `background` so scrolling rows don't show through it. But with `border-collapse: collapse`, the cell's `border-bottom` belongs to the collapsed **table** border, not the cell, and Chrome paints it at the table's static position — so the divider scrolls away with the rows and the pinned header is left with no bottom line.

**Fix:** draw the divider as an inset box-shadow on the sticky cell instead (painted with the cell, so it stays pinned), and give the cell a background:

```css
.stats-table thead th { position: sticky; top: 0; background: #1e1e1e; box-shadow: inset 0 -1px 0 #444; }
```

## Form controls don't inherit `font-feature-settings`/smoothing; the `font` shorthand resets them

Regular elements (`<span>`) inherit `font-feature-settings` and `-webkit-font-smoothing`, but form controls (`input`, `button`, `textarea`, `select`) often don't pick them up the same way. Symptom: an editable input renders a font's **default** glyph shapes while the static text beside it shows a character variant — same family and size, but it reads as "a different font/style."

Worse, the **`font` shorthand resets non-constituent font longhands to their initial values** — including `font-feature-settings`. So `font: inherit` (common on inline-edit widgets) silently drops `font-feature-settings`, setting it back to `normal`.

**Fix:** set the typographic props explicitly on the control, and re-declare `font-feature-settings` *after* any `font:` / `font: inherit`:

```css
.my-input   { font-family: inherit; font-weight: inherit; font-feature-settings: "cv11"; -webkit-font-smoothing: antialiased; }
.inline-edit { font: inherit; }
.inline-edit { font-feature-settings: "cv11"; }  /* must come AFTER `font: inherit`, else the shorthand wipes it */
```

Real case: Hanken Grotesk `cv11` applied via a `.vpl` wrapper showed on display spans but not on the edit `<input>`s, so typed text looked like a different style of the same font.

## Aligning bordered-input text with borderless text needs sub-pixel margins at fractional DPI

To make text typed in a bordered input line up with static text shown without a box, offset the input by its own inset — a negative margin of `(border + padding)` on the alignment side (e.g. `margin-left: -(1px border + 6px padding)` to left-align, `margin-right` to right-align). The nominal value is often **off by ~0.5px** because at fractional device-pixel ratios (Windows 125%/150% display scaling) the 1px border and px paddings round to a non-integer number of CSS pixels. Tuning landed on `margin-left: -6.5px` — a half-pixel — where `-7px` overshot one way and `-6px` the other.

If half-pixels bother you (they can still leave ≤0.5px error since glyphs snap to device pixels), drop the layout border — draw the box edge with `outline` or `box-shadow`, which take no layout space — and zero the padding on the alignment side, so the input's text origin equals the display text origin with no compensation needed.

## Native `<input type="date">` resists CSS sizing — pin a width, don't fight the shadow DOM

Chrome's date control has a minimum intrinsic box width (calibrated for ~16px text) that **ignores** `width: auto` / `fit-content` / `min-content` and any smaller column — instead it overflows, and the surplus shows as a gap between the date text and the right-pinned calendar icon.

What backfires:
- `width: auto` / `fit-content` / `min-content` → no effect; the box stays at its wide default.
- `::-webkit-datetime-edit { flex-grow: 0 }` → **collapses the date text to zero width**. Its UA default is `flex: 1 1 0%`; turning off grow while leaving the `0%` basis means zero width. Even `flex: 0 1 auto` didn't shrink the outer box.

What works:
- An **explicit pixel `width`** (≥ the content) is the only reliable lever to shrink the box and pull the icon up next to the date.
- The shadow `::-webkit-datetime-edit` does **not** reliably inherit `font-variant-numeric` (tabular figures) or `font-feature-settings` (e.g. `cv11`) from the host — set them on the pseudo-element explicitly if the digits must match adjacent static text.
- `::-webkit-calendar-picker-indicator { padding: 0; margin-inline-start: <n>px }` controls the icon's spacing/padding.
- For pixel-perfect layout (no gap, full control), replace the native field: a styled text input plus a button that calls `input.showPicker()`, or an `opacity: 0` date input overlaying a custom field.

Verified in Chromium, June 2026. Note these `-webkit-` pseudo-elements are Chrome/Edge/Safari only.

## A flex-grow `<input>` won't reliably fill-and-truncate — put it in a grid `1fr` cell

Goal: an `<input>` that fills the leftover width of a row and truncates, beside a fixed-width sibling. The obvious `flex: 1 1 0; min-width: 0` on the input **does not reliably shrink it** — it overflows its flex container to the right, even with `min-width: 0` on the input and every ancestor, even after forcing `flex-basis: 0` / `width: 0`. Form controls keep an intrinsic preferred width that flex-shrink doesn't overcome here.

It gets worse when that flex line is itself a **grid item spanning a flexible (`1fr`) track**: the input's intrinsic width blows the `1fr` track wide, stretching the whole line past where it should end — and `min-width: 0` *and* `overflow: hidden` on the grid item both fail to contain it (a Chromium quirk: a flex-container grid item ignores them for track sizing).

**Fix: don't flex-grow the fill — use a grid `1fr` cell and let the input fill it with plain `width: 100%`.** A `1fr` track is sized from free space (definite, not content), so the input fills a definite cell with the base `width: 100%` and no flex-shrink is involved, so it can't overflow.

```css
/* row: [label][fixed input][label][filling input] */
.row { display: grid; grid-template-columns: auto 170px auto 1fr; align-items: center; column-gap: 8px; }
.row input { min-width: 0; }   /* keeps the 1fr cell from blowing out to the input's intrinsic width */
/* inputs fill their cells via the base `width: 100%`; no flex on them */
```

Rule of thumb: for "fill the rest and truncate," reach for a grid `1fr` cell, not `flex: 1` on the control. Flex-grow on an `<input>`/`<select>` is the unreliable path.

