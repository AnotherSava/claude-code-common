# OSM tagging reality when selecting "places worth seeing"

Measured while building a POI-discovery pipeline across Paris, Prague, Kyoto, Mexico
City, Marrakesh, Lisbon, Detroit and Vancouver. The recurring lesson: a tag whitelist
that works beautifully in one city fails differently in the next, and the biggest
landmarks are often the ones with no attraction tag at all.

## A naive tag pull is unusable

Querying `tourism=*` / `historic=*` / `leisure=*` wholesale returns overwhelmingly
junk. Paris: 15,790 elements, of which 17% trail signage, 16% private residential
gardens, 13% hotels — museums and attractions together about **3%**.

Key-level counts explain why:

- `tourism=information` is **36.9%** of the whole `tourism` key, and ~95% of it is
  hiking guideposts, boards and route markers
- `historic=memorial` is **22%** of the `historic` key; `historic=castle` is 2.4% and
  is nearly matched by `historic=charcoal_pile`
- `leisure=garden` is 1.5M objects globally with **3.4% named** and 0.2% carrying
  wikidata — functionally a landuse tag for private gardens

There is no community-standard whitelist to import. The OSM wiki's "Points of
interest" page explicitly declines to define one. Product taxonomies exist (OsmAnd
categories, OpenTripMap "kinds") but none is normative.

## The dominant polluter is different in every city

This is the part that does not generalise, so budget a tuning pass per city:

| City | Dominant junk |
| --- | --- |
| Paris | trail signage (17%) |
| Mexico City | `leisure=garden` (49% of the naive pull) |
| Lisbon | 185 private townhouses tagged `historic=castle` (18% of the list) |
| Detroit | **1,016 non-notable churches — 82%** of the curated result |
| Vancouver | 226 churches (54%), plus 289 water-main `man_made=pipeline` if you add that key |

Secondary tags are usually the discriminator, not the primary one: `castle_type` in
(`palace`, `stately`) on `building=house` separates private palacetes from castles;
`natural` in (`tree`, `water`, `bare_rock`) removes street trees and ponds from
`tourism=attraction`; `artwork_type` gates `tourism=artwork` where a wikidata gate
cannot (only 4 of 81 Detroit artworks carry a QID).

## Wikidata coverage is far lower than assumed, and varies fourfold

Commonly claimed as "most notable objects have a `wikidata` tag". Measured on the
named-sightseeing subset:

| City | wikidata coverage |
| --- | --- |
| Prague | 40.0% |
| Paris | 38.0% |
| Marrakesh | 17.9% |
| Mexico City | 14.7% |
| Kyoto | 10.4% |

By tag globally: `historic=castle` 50%, `building=church` 35%, `tourism=museum` 28%,
`amenity=place_of_worship` 14%, `tourism=viewpoint` 1.2%.

So a QID is a usable join key for the famous head and a poor one for the tail. Design
the join as optional enrichment with a name+coordinate fallback. In bulk-imported
North American geographies, QID presence tracks *import history* rather than
prominence — it admitted Detroit micro-playgrounds while dropping the city's signature
riverfront park.

QIDs are also not always the object in front of you: ~2% point at a *subject* rather
than the place (a QID for "metre" on a measurement marker, for Alexandre Dumas on his
statue). Requiring `wdt:P625` filters most of these. It does not catch everything —
a memorial carrying the QID of the *event* it commemorates has a coordinate and
survives the gate, so an already-Latin local `name` should win over a Wikidata label.

## The biggest landmarks often carry no attraction tag

This is the finding that most changes the architecture. Tag predicates reached only
**19% of Detroit's and 9.3% of Vancouver's** named QID-bearing features. Examples,
all verified:

- Michigan Central Station — `building=train_station` + wikidata, nothing else
- Renaissance Center — `building=commercial` + wikidata
- Fisher Building — `building=office` + wikidata
- Eastern Market — `place=neighbourhood` + `landuse=commercial`
- Belle Isle — `leisure=nature_reserve` + `place=island`, not `leisure=park`, not `tourism=*`

The fix is a **second selection path independent of the whitelist**: select any named
element carrying a QID, whatever its tags, and let a prominence score decide. Exclude
keys that are never destinations however famous (`highway`, `boundary`, `route`,
`landuse`, `place`) — the city's own boundary relation otherwise outranks everything
inside it.

Some features remain unreachable by any predicate: linear or district features that
OSM models as infrastructure with no single entity. Stanley Park Seawall is ~50
`highway=cycleway`/`footway` ways with no relation and no QID; Detroit RiverWalk is
~15 `highway=path` ways. Recovering these needs synthetic grouping of same-named ways,
which risks inventing entities.

## Prominence ranking: use a percentile, not an absolute cutoff

Wikidata sitelink count is a good free prominence signal, but an absolute threshold
encodes *city fame* rather than POI quality:

| City | top POI sitelinks |
| --- | --- |
| Paris (Eiffel Tower) | 189 |
| Lisbon (Torre de Belém) | 57 |
| Vancouver (Stanley Park) | 32 |
| Detroit (DIA) | 29 |

Cut by rank or percentile so one constant serves every city. Also decide explicitly
what rank the unranked get — half of a typical city has no QID at all, and in Detroit
it was 87%.

## Municipal boundaries are the wrong query bound

An `area()`-restricted query cannot return what sits outside the city line, and no
downstream filter can recover it. Real losses: The Henry Ford (Michigan's most-visited
attraction, in Dearborn), the city-owned Detroit Zoo (in Royal Oak), Capilano
Suspension Bridge and Grouse Mountain (District of North Vancouver), the Museum of
Anthropology and Wreck Beach (UBC, unincorporated).

Bound by distance from the centre instead — what makes somewhere belong on a city's
map is being close enough to reach and worth reaching. A radius fix cannot be tuned
per-attraction though: for Detroit, 16 km catches Dearborn but not the Zoo, 18 km
catches the Zoo but not Cranbrook, and 35 km sweeps in half of Oakland County. ~25 km
covered every measured case except one genuine day trip.

The cost is real: Vancouver went from 693 to 2,190 POIs, and suburban civic buildings
(a city hall, a public library, an airport) began outranking Stanley Park on sitelinks.
Distance needs to count against prominence, not just bound it.

## Cheap wins worth knowing

- **Absence of hours is not uniformly "unknown".** A bridge, plaza, viewpoint or public
  park with no `opening_hours` is *always accessible*; a museum without one is genuinely
  unknown. Splitting the no-data bucket by category converts a large slice of apparent
  missing data into a confident answer.
- **`opening_hours` coverage is very low**: 18% (Paris), 12% (Kyoto), 10% (Mexico City)
  on a curated whitelist. By category, `tourism=museum` 54%, `gallery` 23%,
  `attraction` 9%, `place_of_worship` 5%, `viewpoint` 2%.
- **Last admission has no reliable tag** in OSM or Places. A museum closing at 18:00
  with last entry at 17:00 makes a 17:30 arrival worthless and passes every check.
- **Names carry invisible characters.** A Lisbon parish name begins with U+200B, which
  breaks exact-match dedup and Wikipedia title joins.
- **Latin-script labels are not guaranteed.** Central Kyoto: 3.7% of names are pure
  ASCII, `name:en` covers 31%, and **65.7% have no Latin-script label from any tag**.
- **Dedup by name+coordinate, not by QID.** Lisbon had 13 multi-element QIDs (2.9%)
  against 30 names repeating across 65 elements, most without a QID. QID merging is
  also unsafe alone: one QID spanned a cable-car line *and* both its stations, another
  a viewpoint and its adjacent garden, a third the species *Tipuana tipu* on three
  separate street trees.
