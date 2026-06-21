# MapLibre GL JS: basemaps, SDF icons, and style switching

## Free / freemium base-map providers (MapLibre-compatible vector styles)

- **OpenFreeMap** — no key, no signup. `https://tiles.openfreemap.org/styles/<name>`
  where name ∈ liberty (colorful, Google-like), bright, positron (light/minimal).
- **Carto** — no key. `https://basemaps.cartocdn.com/gl/<name>-gl-style/style.json`
  where name ∈ voyager (Google-like), positron, dark-matter (dark).
- **MapTiler** — free key required (100k tiles/mo). Sign up at cloud.maptiler.com.
  `https://api.maptiler.com/maps/<id>/style.json?key=<KEY>`, id ∈ streets-v2,
  hybrid (satellite+labels), dataviz (light), outdoor-v2, aquarelle (watercolor),
  topo-v2, winter-v2, ocean, toner-v2, basic-v2, streets-v2-dark, backdrop, landscape.
- **Mapbox** styles are NOT usable with MapLibre — their TOS requires Mapbox GL JS.

## Data-driven colored markers via SDF icons

To recolor one icon per-feature with `icon-color`, the image must be added as SDF.
Draw the shape on a canvas and add it with `{ sdf: true }`. A small blur on the
canvas (`ctx.filter = "blur(2px)"`) turns the hard fill into a distance ramp at the
edge, which the SDF shader renders as smooth, recolorable anti-aliasing — no real
distance-transform needed. Then `paint: { "icon-color": ["match", ["get","country"], ...] }`.

## addImage name collisions

`map.addImage("star", ...)` THROWS `An image named "star" already exists` when the
base style's sprite already defines that name (OpenFreeMap liberty has a "star").
Namespace custom images, e.g. "visited-star".

## setStyle wipes the overlay — re-add idempotently

`map.setStyle(url)` removes all custom sources/layers/images. Re-add them on the
`styledata` event. But `styledata` fires repeatedly and mid-transition, so:
- Guard EACH add individually (`if (!map.getLayer(id)) map.addLayer(...)`), not an
  all-or-nothing top guard — a partial state otherwise throws "already exists".
- Use `map.setStyle(url, { diff: false })` for a clean swap.

## Cross-provider cluster label fonts

`text-font` must name a font the active style's glyphs provide, which differs per
provider. Reuse whatever the loaded style already references:
scan `map.getStyle().layers` for the first `layout["text-font"]` array and use it.

## Local serving

Fetching GeoJSON needs http:// (not file://). If the data dir is a sibling of the
web dir, a server rooted at the web dir can't reach it — keep data INSIDE the served
root (e.g. web/data/) so the bundle serves from one directory.
