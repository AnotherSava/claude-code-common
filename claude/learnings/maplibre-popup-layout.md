# MapLibre GL JS popups: clipping, anchoring, and focus

Companion to `maplibre-gl-basemaps.md`, which covers tiles, SDF icons and clustering.
This covers putting non-trivial content — an image, a hover disclosure — inside
`maplibregl.Popup`. Verified against MapLibre GL JS 4.7.1 in Chrome.

Everything here fails **silently**: no console warning, no error, just a popup that is
positioned wrong or a panel that cannot be clicked.

## `overflow-y: auto` on the popup content clips absolutely-positioned children

Capping a popup's height with

```css
.maplibregl-popup-content { max-height: 45vh; overflow-y: auto; }
```

also computes `overflow-x` to `auto` (per CSS overflow: a non-`visible` value on one
axis forces the other away from `visible`). The content box becomes a scroll container
and clips an absolutely-positioned descendant **on all four sides** — a tooltip 50 px
below the box is not merely invisible, it is not hit-testable: `elementFromPoint` there
returns the map canvas.

Fix: move the scroller off the popup content onto an **inner wrapper around the prose
only**, and make the content a flex column with the height cap:

```css
.maplibregl-popup-content { max-height: 46vh; overflow: visible;
                            display: flex; flex-direction: column; padding: 0; }
.prose { overflow-y: auto; min-height: 0; overscroll-behavior: contain; }
```

The popup still caps and the prose still scrolls, but overlays escape.

### They escape the popup, not the map

`.maplibregl-map` carries `overflow: hidden`, and the popup lives inside it. A panel
that leaves the popup's own footprint gets clipped at the map's edge. Keep overlays
geometrically within the popup (anchor bottom-right, open upward with `bottom: 100%`),
or put them in the **top layer** via the `popover` API, which escapes every clip —
CSS anchor positioning resolves correctly despite the popup's `transform`, but is not
in Firefox yet.

## An image without `aspect-ratio` re-anchors the popup off the map

MapLibre measures `_container.offsetHeight` **once**, inside `_update()`, and never
re-measures. Anchor choice is made from that measurement. An `<img>` with no reserved
height is 0 px tall at `setHTML()` time and grows on load, so the popup is anchored as
if it were short and then overflows upward.

Measured on a popup 300 px from the top of the map: `top: 214` before load, `top: -181`
after — clipped away entirely, with no error. With `aspect-ratio: 3/2` the height was
identical before and after and the top stayed positive.

```css
.shot img { display: block; width: 100%; aspect-ratio: 16 / 9;
            object-fit: cover; background: var(--chip); }
```

This is load-bearing, not styling. Anyone who later swaps it for `height: auto` for a
"nicer fit" reintroduces the jump. Explicit `width`/`height` attributes work too.

Shrinking is safe — removing a broken image only makes the popup smaller, which can
never push it off the map.

## The constructor's `maxWidth` beats your stylesheet

MapLibre writes its default `max-width: 240px` **inline** on `.maplibregl-popup`:

```js
const defaults = { closeButton: true, closeOnClick: true, focusAfterOpen: true,
                   className: "", maxWidth: "240px", subpixelPositioning: false };
this._container.style.maxWidth = this.options.maxWidth;
```

So `.maplibregl-popup-content { max-width: 320px }` silently does nothing. Widening
takes **both** the constructor option and the CSS — changing one looks like the change
didn't work.

## `focusAfterOpen` breaks `:focus-within` disclosures

`Popup._focusFirstElement` runs from both `addTo` and `setDOMContent` and focuses the
first match of a selector list that includes `a[href]`, `[tabindex]`, and
`button:not([disabled])`. Add a `<button>` to popup content and it receives focus on
open — so a CSS `:focus-within` disclosure is **expanded on every popup**.

```js
new maplibregl.Popup({ focusAfterOpen: false, maxWidth: "296px" })
  .setLngLat(…).setHTML(html).addTo(map);
popup.getElement()?.querySelector(".maplibregl-popup-close-button")?.focus();
```

With no focusables in the content, focus lands on the close button anyway — so focusing
it by hand preserves the previous behaviour exactly.

## Hover panels: zero gap, and never a `margin` gap

A panel offset from its trigger by `margin` leaves a band where neither element is under
the pointer, so the panel closes mid-traverse and its links are unreachable. Use
`bottom: 100%` with no gap, or `padding`, and nest the panel **inside** the trigger
wrapper so hovering the panel keeps `:hover` alive on the wrapper.

Use `visibility: hidden/visible` rather than `display: none` or opacity: it hides the
panel *and* takes its links out of the tab order, and restores both together. Reveal
with `.wrap:hover > .panel, .wrap:focus-within > .panel`.

`role="note"`, not `role="tooltip"` — a tooltip may not contain interactive content, and
a credits panel usually holds links. Omit `aria-expanded` entirely when CSS can open the
panel without JS updating the attribute; an attribute that lies is worse than none.

## `setHTML()` rebuilds the DOM, so listen at the document

Any per-popup listener has to be re-bound after every `setHTML()`. One capture-phase
listener installed once survives by construction:

```js
document.addEventListener("error", (e) => {
  if (e.target instanceof HTMLImageElement) e.target.closest("figure")?.remove();
}, true);
```

Capture because `error` does **not** bubble. (An inline `onerror=` in the HTML string
also works, but keeps JS in the template.)

## The tip stays hardcoded white in dark mode

`.maplibregl-popup-tip` is a CSS triangle: `border: 10px solid transparent` with one
side coloured `#fff`. On a dark popup it hangs a white arrow off the corner.

Colour it **per anchor**, not with one blanket rule — setting all four borders fills the
transparent sides and squares the triangle off:

```css
.maplibregl-popup-anchor-top .maplibregl-popup-tip,
.maplibregl-popup-anchor-top-left .maplibregl-popup-tip,
.maplibregl-popup-anchor-top-right .maplibregl-popup-tip { border-bottom-color: var(--bg); }
.maplibregl-popup-anchor-bottom .maplibregl-popup-tip,
.maplibregl-popup-anchor-bottom-left .maplibregl-popup-tip,
.maplibregl-popup-anchor-bottom-right .maplibregl-popup-tip { border-top-color: var(--bg); }
.maplibregl-popup-anchor-left .maplibregl-popup-tip { border-right-color: var(--bg); }
.maplibregl-popup-anchor-right .maplibregl-popup-tip { border-left-color: var(--bg); }
```

The close button needs the same attention once an image sits behind it — a bare glyph in
a muted colour disappears against a dark photograph. A small circular scrim in `--bg`
fixes it.
