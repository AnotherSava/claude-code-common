# CSS Anchor Positioning

Native browser-managed positioning for tooltips, popovers, dropdowns — with automatic viewport-edge flipping, no JavaScript. Chrome 125+ / Edge 125+ (shipped May 2024). Firefox and Safari: not yet at time of writing. For Chrome-only contexts (extensions, internal tools, controlled deployments) this replaces the whole "compute position on mousemove + detect overflow + flip" JS stack with ~10 lines of CSS.

## Core mechanism

Two sides:

1. **Anchor element** declares an anchor-name.
2. **Positioned element** references that name and positions itself relative to the anchor's edges.

```css
.card {
  anchor-name: --card-anchor;
  anchor-scope: --card-anchor;  /* see "scoping" below */
}

.card-tip {
  position: fixed;               /* or absolute */
  position-anchor: --card-anchor;
  top: anchor(bottom);           /* tooltip's top edge = anchor's bottom edge */
  left: anchor(left);            /* tooltip's left edge = anchor's left edge */
}
```

The `anchor(<side>)` function resolves to the coordinate of that side of the anchor element. You can use it wherever a length is expected (`top`, `left`, `right`, `bottom`, or inside `calc()` for offsets like `calc(anchor(bottom) + 4px)`).

## Scoping: `anchor-scope` for per-instance anchors

Without `anchor-scope`, `anchor-name: --foo` declared on many elements (e.g. every card in a grid) creates ambiguity — a positioned element with `position-anchor: --foo` resolves to the *nearest* anchor in tree order, which isn't necessarily the parent.

`anchor-scope: --foo` on an element limits the visibility of `--foo` to that element's subtree. Set it on the anchor itself to scope the anchor name to its own descendants:

```css
.card {
  anchor-name: --card-anchor;
  anchor-scope: --card-anchor;  /* --card-anchor outside this card's subtree is invisible */
}
```

Now each card's `.card-tip` (a descendant) resolves `--card-anchor` to its own parent card, not some other card elsewhere in the document. This lets every card share the same anchor-name without collision.

## Automatic viewport-edge flipping

The killer feature: `position-try-fallbacks` tells the browser to try alternate positions when the declared one would overflow the viewport.

```css
.card-tip {
  position: fixed;
  position-anchor: --card-anchor;
  top: calc(anchor(bottom) + 4px);
  left: anchor(left);
  position-try-fallbacks: flip-block, flip-inline, flip-block flip-inline;
}
```

Comma-separates alternative positions to try in order. Space-separates transformations combined in one alternative.

- `flip-block` swaps block-axis properties (`top ↔ bottom`, `inset-block-start ↔ inset-block-end`). Tooltip that was below the anchor flips above.
- `flip-inline` swaps inline-axis properties (`left ↔ right`, `inset-inline-start ↔ inset-inline-end`). Tooltip that was left-aligned flips right-aligned.
- `flip-block flip-inline` does both in one alternative (diagonal flip).

The browser picks the first alternative (including the declared position) that fits without overflow. Four corners of the viewport, four permutations: all handled by the one-line fallback list above.

Empirically verified with a 800×700 viewport and `.card-tip` at 375×275:

| Anchor position | Resolved tooltip placement     |
| --------------- | ------------------------------ |
| Top-left        | below-left (declared)          |
| Top-right       | below-right (flip-inline)      |
| Bottom-left     | above-left (flip-block)        |
| Bottom-right    | above-right (flip-block flip-inline) |

No overflow in any case.

## When positioned vs. anchor coordinates differ

`position: fixed` + `top: anchor(bottom)` places the tooltip in viewport space using the anchor's viewport-space coordinates. This works even when the anchor is inside a scrolling container — `anchor()` always resolves to the anchor's actual rendered position. If the anchor scrolls out of the viewport, the tooltip follows it (still anchored to its bottom edge, which is now off-screen).

`position: absolute` positions relative to the nearest containing block. Use this when the tooltip should move with the document (not stay fixed to the viewport) and there's a containing block at a sensible level.

For hover tooltips, `fixed` is usually right — the tooltip appears over other content regardless of scroll state.

## Custom positions: `@position-try` at-rule

For more than the four flip keywords, define named custom try-positions:

```css
@position-try --above-right {
  top: auto;
  bottom: anchor(top);
  left: auto;
  right: anchor(right);
}

.tooltip {
  position-try-fallbacks: flip-block, --above-right;
}
```

Use when the default position should be e.g. `below-left` but the fallback should be `above-right` rather than the mirror `above-left` that `flip-block` gives.

## Gotchas

- **Don't `position-try-fallbacks` without `position-anchor` set** — the fallbacks silently have no effect.
- **`anchor()` inside `calc()` only works for same-axis values.** `calc(anchor(bottom) + 4px)` is fine for `top`. `calc(anchor(bottom) + 4px)` used as `left` will resolve oddly — `anchor(bottom)` is a block-axis value and doesn't belong in inline-axis properties.
- **`anchor-scope: all` vs named.** `anchor-scope: all` scopes every anchor-name on the element; `anchor-scope: --foo` scopes only that one. Use the named form in libraries to avoid clobbering someone else's scope.
- **Legacy `position-try-options` name.** Some older drafts and articles use `position-try-options`. Current name is `position-try-fallbacks`. Both shipped in some intermediate Chrome versions; prefer the final name.
- **No mouse-follow.** Anchor positioning anchors to an element. Tooltip stays put while the cursor moves within the anchor. This is usually *better* UX (stable, no jitter) but it's a behavior change from typical JS tooltip libraries that track the cursor.
- **Debugging via headless Chromium.** Playwright's `chromium.launch()` ships a recent Chromium that supports anchor positioning. Useful for empirical verification without a real Chrome instance — hover a corner, screenshot, check `getBoundingClientRect()` against `innerWidth/innerHeight` to confirm no overflow.

## Migration pattern: replacing JS mouse-follow tooltips

Typical JS tooltip code attaches a `mousemove` listener, reads `e.clientX/Y`, sets `tip.style.top = mouseY + "px"`. To migrate:

1. Add `anchor-name` + `anchor-scope` to the hoverable element (e.g. `.card`).
2. Change the tooltip's `position: fixed` to keep that, but add `position-anchor`, a `top`/`left` pair with `anchor(...)`, and `position-try-fallbacks`.
3. Delete the `mousemove` listener and any associated setup code.
4. Keep the `:hover > .tooltip { display: block }` rule — hover detection is still CSS-native.

The tooltip no longer follows the cursor, but it now:
- Positions correctly at viewport edges (no overflow / clipping).
- Doesn't flicker when the cursor moves within the hoverable.
- Has zero JS overhead on mousemove.
- Serializes trivially into standalone HTML exports (no `positionTooltip.toString()` plumbing).
