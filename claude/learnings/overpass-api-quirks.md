# Overpass API: silent failures, output modes, and query bounds

Notes from building a POI-discovery pipeline against `overpass-api.de`. Every item
below was reproduced live, not read from documentation.

## Failures arrive as HTTP 200

Overpass does not signal most failures through status codes.

| Symptom | What you get |
| --- | --- |
| Query exceeded its timeout | **HTTP 200**, valid JSON, `"elements": []`, and a `remark` key: `runtime error: Query timed out in "query" at line N` |
| Query partially completed | **HTTP 200**, *partial* elements plus the same `remark` — plausible-looking data that is silently incomplete |
| Area id derived from a node | **HTTP 200**, zero elements, **no error at all** |
| Server overloaded | HTTP **504 with an XHTML body**, which breaks `response.json()` before any status check runs |

Validate before caching or using a response:

- reject when `remark` is present — this catches partial results, which is the
  dangerous case
- reject when `elements` is empty (unless emptiness is genuinely expected)
- reject when `osm3s.timestamp_osm_base` is older than about a week

That last one matters because **mirrors serve stale extracts non-deterministically**.
The main endpoint returned data current to the minute while a mirror returned an
extract five weeks old on one call and seven weeks old minutes later. Pin one
endpoint rather than failing over; a silent failover trades a loud error for wrong
data. Note that `overpass-api.de` itself round-robins across named backends
(`lambert`, `gall`), so pinning the public hostname does not pin the backend.

## Output modes are mutually destructive

`out center geom;` is a trap: the **later mode wins**, so it returns geometry and
**zero centres**. Verified live — 6 ways got geometry, every relation got no
coordinate at all.

`out tags geom;` means *tags only*, and the `tags` modifier **suppresses member
listing**. Relations therefore come back with no members and no geometry. Plain
`out geom;` returns tags *and* members with geometry.

To get geometry for ways and centres for relations, use two statements over the same
result set and merge by `(type, id)`:

```
(...)->.result;
.result out tags geom;
.result out tags bb;
```

## `out center` is a bounding-box centre, not a point inside the feature

For anything concave or curved it can land outside its own polygon. Measured: 25 of
316 closed named ways (7.9%) placed their pin outside themselves. A 1070 × 200 m
curved bridge outline put its centre 178 m away, off the bridge entirely.

Compute a pole of inaccessibility instead (`shapely.ops.polylabel`, falling back to
`representative_point()`, never `centroid` — a centroid can also fall outside a
concave shape).

`out bb` costs the same as `out center` and yields the full bounding box, giving you
both a midpoint and the feature's **extent** — extent is what separates a museum
(~100 m) from a 38 km peninsula.

## Relations need three different reductions

Real data contains all three, and handling only the first loses the rest:

- **Areas** — the outer ring is routinely split across several member ways, none
  closed on its own. Merge the members as linework and polygonize (`linemerge` +
  `polygonize`); concatenating their points in listed order produces a
  self-intersecting mess. Note `buffer(0)` on such a ring often returns a
  *MultiPolygon*, so keeping only plain `Polygon` results silently drops features.
- **Routes** — a race circuit or ferry line has no interior. Roles look like
  `forward`, `pit_lane`, `start-finish`. Use the midpoint of the merged line.
- **Node-only relations** — a transit station lists platforms and entrances as
  *nodes*, which arrive with `lat`/`lon` and no `geometry` key at all.

Fetching member geometry is cheap for small features and expensive for large ones:
sub-kilometre relations cost 60–90 KB for a whole city, while a handful of
kilometre-scale ones (a 31 km inlet, a 38 km peninsula) cost megabytes. Bound the
geometry pass by extent.

## Bound queries with a bbox, not `around:`

`around:` performs a real radial search; a bbox uses the spatial index. A 25 km
`around:` across ~30 clauses returned **HTTP 504 on every attempt**, while the
equivalent bbox completed normally. Use a bbox for the query and apply a haversine
filter locally to trim the corners back to a true circle.

## Rate limits

The public instance allows **2 concurrent slots per IP** and roughly 10k requests/day
with a 180 s default timeout. HTTP 429 arrived after two back-to-back city-sized
queries, recovering in 30–120 s. Cache per city; never query per user request.
Set a descriptive `User-Agent` — a library default violates the usage policy.

## Selecting is not the inverse of rejecting

A union query is an OR over predicates, so an element enters on **one** matching tag
and arrives carrying every other tag it has. A value can therefore be absent from
your whitelist and still be present in the output. Implementing "exclude
`historic=yes`" as a reject-if-present filter deleted a genuine top-25 POI that had
arrived via `amenity=theatre`.

Keep a *selection* predicate list, never a reject list, and a separate ordered
*category precedence* table for display — elements routinely match several families
at once (a tower that is both `tourism=attraction` and `historic=fort`).
