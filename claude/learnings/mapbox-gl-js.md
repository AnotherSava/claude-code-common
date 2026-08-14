# Mapbox GL JS (v3): projection, styles, and the Standard-style custom-source trap

Mapbox GL JS is the proprietary renderer MapLibre forked from; API is ~95% shared.

## Setup
- `mapboxgl.accessToken = "pk...."` is REQUIRED — without a token the map halts
  rendering entirely (even a blank style triggers the token error).
- CDN: https://unpkg.com/mapbox-gl@3/dist/mapbox-gl.js (+ .css).

## Projection
- v3 defaults to a 3D GLOBE at low zoom (not flat Mercator like MapLibre). Force
  flat with `projection: 'mercator'` in the Map options.

## Style URLs  `mapbox://styles/mapbox/<id>`
streets-v12, satellite-streets-v12 (hybrid), light-v11, dark-v11, outdoors-v12,
navigation-day-v1, standard (v3 flagship 3D).

## API differences from MapLibre
- `GeoJSONSource.getClusterExpansionZoom(clusterId, callback)` is CALLBACK-based,
  not promise-based (MapLibre v4 made it a promise).

## Clustering: `clusterMaxZoom` is the LAST zoom that still clusters
`clusterMaxZoom: 8` keeps points clustered AT z8; they separate only above it. So a
camera the app lands on programmatically (an opening view, a "fly to X") must sit
strictly ABOVE the cutoff, not at it — an off-by-one is invisible in review and
obvious on screen. Couple them in code (`clusterMaxZoom: LANDING_ZOOM - 1`) so the
invariant can't drift.

The failure is worse when the app renders its own labels and suppresses the
basemap's for the same features: a clustered point is filtered out of the symbol
layer (`filter: ["!", ["has", "point_count"]]`) AND has no basemap label left, so
the city you deliberately framed carries no name from either source — the user sees
an anonymous count bubble. Verify with
`map.queryRenderedFeatures({ layers: ["clusters"] })` at the landing zoom: a
non-empty `point_count` there is the bug. Whether a given city clusters depends on
`clusterRadius` (screen px) against its nearest neighbour, so it bites only part of
a dataset — spot-checking two cities proves nothing.

## The Standard (v3) custom-source trap — AVOID for dynamic overlays
Standard is an "import" style (basemap fragment + slots). Adding your OWN GeoJSON
source/layers dynamically does NOT work reliably:
- Source is ORPHANED: keeps `_data` but never tiles/renders (querySourceFeatures
  returns 0). True on first load AND on setStyle switches.
- `slot: "top"` is needed so custom layers sit above the imported basemap, but does
  NOT fix the orphaned source.
- Self-heal fails: after `removeSource('x')`, `getSource('x')` is falsy yet
  `addSource('x')` throws "already a source with ID x" — inconsistent internal state.
- Classic styles (streets-v12 etc.) have none of these problems.
Verdict: if your app overlays custom data and switches styles, exclude Standard
(or recreate the whole Map instance for it).

## Runtime style customization (no Mapbox Studio needed)
After a style loads, override layers directly; re-apply on every `styledata` (setStyle resets it):
- Hide roads: roads are MANY layers — surface `road-*`, bridges `bridge-*`, tunnels
  `tunnel-*`, each split into `-case` (outline) + fill, per hierarchy class (motorway-
  trunk / primary / secondary-tertiary / minor / street / *-link / path / steps), plus
  one-way arrows, rails (`*-rail*`), ferries, and labels/shields. Streets v12 ≈ 87 of
  them. Hide via id match /road|bridge|tunnel|motorway|street|ferry/ →
  `setLayoutProperty(id, "visibility", "none")`.
- Borders: `admin-0-boundary` (countries), `admin-1-boundary` (regions/states),
  `admin-0-boundary-disputed`. `setPaintProperty(id, "line-color", ...)`.

## Globe atmosphere (the glow) — `map.setFog(...)`
The halo around the globe is the `fog` property. Streets/Satellite set a blue
atmosphere (`high-color: hsl(210,100%,80%)`, zoom-interpolated `space-color` +
`star-intensity`); Light/Dark v11 set it flat white/black = no glow. Copy Streets'
fog onto them with setFog to add the halo.

## Attribution & logo are MANDATORY (TOS)
Don't remove or fade the Mapbox logo (`.mapboxgl-ctrl-logo`) or the attribution —
required by Mapbox TOS, and OSM data needs the OSM credit (ODbL). Compliant declutter:
`new mapboxgl.Map({ attributionControl: false })` + `addControl(new
mapboxgl.AttributionControl({ compact: true }))` → collapses to an ⓘ button.

## Custom controls (IControl) — the control-button CSS trap
`map.addControl(new MyControl(), "top-right")` where `onAdd` returns a
`<div class="mapboxgl-ctrl mapboxgl-ctrl-group">` means **every `<button>` inside your
control inherits Mapbox's own control-button rules** from mapbox-gl.css — which quietly
override your styles by specificity:
- `.mapboxgl-ctrl-group button` — forces fixed **29×29px** sizing, transparent bg, no
  border-radius on the button itself (0,1,1).
- `.mapboxgl-ctrl-group button:last-child { border-radius: 0 0 4px 4px }` — rounds only the
  **bottom** two corners (0,2,1). Symptom: your button shows square top corners, rounded
  bottom ones, no matter what `border-radius` you set at (0,1,0)/(0,0,1).
- `.mapboxgl-ctrl button:not(:disabled):hover { background-color: #eee }` — forces a light
  grey hover (0,3,1). Symptom: your `:hover` background "blends into the panel" / won't take.
Two fixes:
- **Out-specify** — prefix with enough extra classes to beat the numbers above, e.g.
  `.panel .row .submit:hover:not(:disabled)` clears the `#eee` hover (which is a high 0,3,1).
  Whack-a-mole: each Mapbox rule needs its own higher-specificity counterpart.
- **Better: escape the group** — don't put styleable buttons inside the `mapboxgl-ctrl-group`
  DOM at all. Give your container only a positioning class (drop `mapboxgl-ctrl-group`), or
  render the interactive panel/popup outside the control element, so none of the
  `.mapboxgl-ctrl(-group) button` rules apply and your CSS wins at base specificity.
Confirm which rule is winning by `curl`-ing the pinned mapbox-gl.css and reading the actual
selector + value, rather than guessing at the override.

## Built-in control layout: corners stack, and ScaleControl's width is a ceiling
- **A corner container stacks its controls vertically** — `.mapboxgl-ctrl-bottom-right` and its three
  siblings are flex columns, so two controls added to the same corner sit one above the other in
  `addControl` order. To lay them out side by side instead — a scale bar to the LEFT of the compact
  attribution ⓘ — override the corner:
  `.mapboxgl-ctrl-bottom-right { display: flex; flex-direction: row; align-items: flex-end }`.
  Row order follows add order, so add the scale first for it to end up leftmost; `align-items:
  flex-end` bottom-aligns a 22px bar against a 24px button so they read as one strip.
- **In a row, give the scale `flex: none`.** Clicking ⓘ expands the attribution leftwards, which
  otherwise squeezes the neighbouring scale bar — and a squeezed ruler no longer matches the distance
  it prints. With `flex: none` the row grows past it instead; even on a 360px-wide map the expanded
  attribution wraps and the bar stays on screen.
- **`ScaleControl`'s `maxWidth` (default 100) is a ceiling, not the drawn width.** The bar renders the
  largest round distance that fits under it, so its pixel length swings between roughly half and all
  of the budget as you zoom — at `maxWidth: 200`, 151px for "30 km" in one view and ~50px in another.
  Pick the number as a budget; don't expect a stable bar length or a proportional bump when raising it.

## Symbol overlays & label placement
- **Label collision priority is TOP-DOWN**: layers higher in the stack are placed
  first and win collisions (that's why country labels beat city labels). An overlay
  added at the bottom has the LOWEST priority — its labels yield to every base label
  and only appear once zoom spreads the collisions out ("appears later than it should").
  To give an overlay's labels priority, insert it ABOVE the layers it should beat —
  e.g. before `country-label` (via the `beforeId` arg of `addLayer`) to beat city +
  state labels but still cede to country/continent. Keep `text-allow-overlap` false so
  they still don't pile on each other; they just win their spot and base labels yield.
- **Settlement label structure (Streets v12)**: `settlement-major-label`,
  `settlement-minor-label`, `settlement-subdivision-label`. Feature props include
  `symbolrank` (prominence — LOWER = more prominent, e.g. Toronto 6 vs Niagara Falls 11;
  drives the `text-size` step expressions), `iso_3166_1` (country, "GB"), `iso_3166_2`
  ("GB-ENG"), and `name`/`name_en`/`name_<lang>`. There is NO `text-variable-anchor`;
  `text-anchor` is `["step",["zoom"],["get","text_anchor"],8,"center"]` → the name sits
  to a data-driven side below z8 but is centered ON the point at z≥8. Consequence: you
  cannot collision-route a base city label off a marker you place at the point — it will
  sit under the marker. Own the label instead (render your own + filter the base one).
- **`querySourceFeatures(source, {sourceLayer})` is TILE-LIMITED**: returns only
  features in currently loaded tiles (viewport + buffer), ignoring layer filters. Great
  for reading base data (symbolrank, iso) for what's on screen; to harvest globally you
  must drive the camera over each area (e.g. `jumpTo` each point, await `idle`). Base
  source/sourceLayer for place labels = `composite` / `place_label`.
- **`map.getLayer(id).sourceLayer` is `undefined`** on the returned layer object — read
  the source-layer via bracket form `layer["source-layer"]` instead.
- **`text-size` is a LAYOUT property** → it CANNOT read `feature-state` (only paint and
  filter can). To size labels per-feature from harvested/derived data, write the value
  into the GeoJSON feature `properties` and `setData` (or bake it at build time), then
  key the size expression on `["get", "<prop>"]`.
- **SDF icons recolor at runtime**: `addImage(id, imageData, {sdf:true})` makes
  `icon-color` paint the icon per-feature (data-driven via `["get",...]`). Pair
  `icon-anchor:"bottom"` (icon sits ABOVE the point) with `text-anchor:"top"` +
  `text-offset` (label BELOW the point) so a marker and its label sit on opposite sides
  of the point and never collide at any zoom.

## Telemetry
GL JS POSTs to `events.mapbox.com/events/v2` (usage analytics). If that host is
blocked/unresolvable → `net::ERR_NAME_NOT_RESOLVED` in console; harmless, map still
works, no public toggle to disable.

## Licensing
Mapbox styles/tiles may only be used with Mapbox's own SDK (TOS); MapLibre can't
legally use them — see maplibre-gl-basemaps.md.

## Token URL restrictions & scopes
The public `pk.` token ships in client JS by design — lock it down with **URL
restrictions** (Account → token settings) so it can't be reused off your domain.

Restriction format rules (the UI rejects the rest):
- **No wildcards.** `*` is rejected outright (`http://localhost:*` fails).
- **No IPs.** Use `localhost`, not `127.0.0.1`.
- **Path is a prefix** — `https://site.com` already authorizes `https://site.com/sub/…`;
  no trailing `/*` needed. Paths are case-sensitive.
- **Port:** if omitted, only 80/443 are allowed. A dev server on another port needs it
  explicitly, e.g. `http://localhost:8000`.
- A request with a **blank `Referer`** under a restricted token returns **403** (so
  `file://` won't work). ≤100 URLs per token. Browser/GL-JS only — not native SDKs.

Practical setup:
- The **Default public token cannot be edited** (only rotated). To add restrictions you
  must **create a new token**. Use **separate prod and dev tokens** (Mapbox best practice)
  — prod restricted to the live domain, dev to `http://localhost:<port>`.
- **Scopes:** the default public scopes (`styles:read`, `styles:tiles`, `fonts:read`)
  already suffice to render a style. Restricting a token needs **no scope change**, and
  both prod/dev tokens are plain public tokens with identical scopes — only the URL list
  differs. (Build-time geocoding via Nominatim makes no Mapbox call, so no geocoding
  scope is needed at runtime.)
- **Don't verify enforcement with server-side curl.** A spoofed `Referer`/`Origin` from a
  shell does not reliably reproduce Mapbox's browser-based enforcement (it returns 200
  regardless). Trust the dashboard config; test blocking in a real browser if needed.

## Diagnosing a blank white globe

The globe, its atmosphere/fog and the Mapbox logo all render from the main thread and need no
tiles — so **a blank white globe with correct chrome means the style loaded but the vector
source did not**. Nothing in the console says so. Two causes look identical; separate them by
whether the TileJSON request was *refused* or *never sent*:

```js
const sc = map.style._sourceCaches['other:composite'];
sc._source._loaded          // false  -> source never finished
sc._source._tileJSONRequest // still an object -> request outstanding
map.style._loaded           // true -> the style itself is fine
```

**1. Sent and refused (403) — a URL-restricted token off its allowed origin.** The tell is that
*everything except tiles works*: style JSON, `sprite.json` and the glyph `.pbf` all return 200,
and `/tokens/v2` reports `TokenValid`, so the token looks healthy and the restriction is the
last thing suspected. Only `/v4/<tileset>` and `styles/.../tiles/...` 403. A wrong **port**
counts as a wrong origin (see the restriction rules above) — serving the same files on 8001
instead of 8000 is enough.

**2. Never sent — the tab is hidden.** GL JS defers source and tile loading while
`document.visibilityState === 'hidden'`. The source cache is created and `_tileJSONRequest`
exists, but no HTTP request is ever issued: nothing in the network panel, no `error` event,
`isStyleLoaded()` false forever, and the globe paints once and sits there. This bites under
browser automation, where the driven tab is often backgrounded — and manually `fetch`ing the
same TileJSON URL *from that page* returns 200, which makes it look even more like an app bug.
**Check `document.visibilityState` before spending time on the token.**

GeoJSON overlays are parsed in the worker too, so a custom star/pin layer stays invisible under
both causes — missing *your own* markers is not extra evidence of a data problem.
