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
