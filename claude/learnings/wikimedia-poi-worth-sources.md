# Judging whether a POI is worth visiting, without a model

Companion to `osm-poi-tagging-reality.md`, which covers *selecting* POIs from OSM.
This covers the next question: given a place and its class, is there anything to see?
Measured across Vancouver (2,190 POIs) and Detroit (1,545) while building a POI
shortlist with a hard constraint of no LLM in the runtime pipeline.

The headline: **prominence and worth are different things, and ranking by prominence
puts an airport, a neighbouring city, two civic buildings and three universities above
the city's best-known park.** Vancouver's sitelink order opens BC Place (53), the
airport (53), New Westminster (42), Rogers Arena (35), then Stanley Park (32).

## Wikivoyage is the only free source that answers "why go"

Every other source says what a thing *is*. Wikivoyage editors are writing a guide, so
a place earns a `{{see}}` or `{{do}}` listing only when somebody thought it worth a
paragraph — and the listing carries the sentence explaining why.

Editorial silence is a sharp signal. Of 22 Vancouver POIs that rank high on sitelinks
and are not sightseeing — the airport, two city halls, a public library, three
universities, four transit stations, two suburban bridges, an arena, an Olympic oval —
**18 have no listing at all**.

Practical notes:

- Parse `{{see}}` and `{{do}}` **only**. `{{listing}}` carries airlines, bus operators,
  consulates and hotels; `{{marker}}` is a map pin with no prose. Including both puts
  FlixBus and the Albanian consulate in the results.
- Template bodies need **brace-matched extraction and a top-level pipe split**. Listing
  prose contains nested templates and piped wiki links —
  `[[Ice hockey in North America|NHL]]` — so a plain `split("|")` truncates the content
  field mid-sentence and drops every field after it.
- **67–80% of listings carry a `wikidata=` parameter**, so the join to a POI set is by
  QID, not by name. Name is the fallback (the guide writes "Hotel Vancouver" where OSM
  has "Fairmont Hotel Vancouver").
- Bound the name fallback by distance. The article set spans a whole metro, so
  "Central Park" and "City Hall" are live collision hazards. Use a generous radius for
  an exact name match (a guide pins a park's entrance, a pipeline pins its pole of
  inaccessibility — Stanley Park's is deep in the forest) and a tight one for partial
  matches.
- Listings are **duplicated** across a city article and its district pages, sometimes
  under two different QIDs. Prefer `see` over `do` when collapsing.

### Find articles by reach, not by name

Wikivoyage splits a metro across one article per municipality, so fetching only
`Vancouver` loses Capilano Suspension Bridge and Grouse Mountain to `North Vancouver`;
only `Detroit` loses The Henry Ford to `Dearborn`, the Zoo to `Royal Oak` and Cranbrook
to `Bloomfield Hills`. This is the same failure as bounding an Overpass query by the
municipal relation.

`list=geosearch` finds them, but **caps `gsradius` at 10 km**, so covering a 25 km reach
takes a grid of overlapping discs. Concentric rings beat a square lattice — a square
grid over a circular reach spends about a third of its requests on corners. 37 points
returned 30 articles for Vancouver and 38 for Detroit, including every municipality
that mattered.

### `see` vs `do` independently encodes the event-venue distinction

Wikivoyage's own taxonomy separates a thing you look at from a thing you attend, and
its editors apply it to exactly the hard case: Detroit's Ford Field, Little Caesars
Arena and Comerica Park are all `do`, never `see`. BC Place's entry is a list of
tenants and fixtures.

The consequence for scoring: **a guide listing on a venue is evidence the programme is
worth attending and says nothing about whether the building is worth looking at.** Score
it as though it did and every guide-listed venue clears the bar — including a suburban
ground listed as "home of the BC High School Championships" and community arts centres
with zero sitelinks between them. What separates the Fox Theatre from Ford Field is a
heritage designation on the fabric, not the listing.

## Wikipedia lead extracts cover what the guide missed

Wikivoyage reaches about a third of a shortlist. For the rest the fallback is usually a
Wikidata description, and those are routinely tautologies — "St. Andrew's Wesley Church"
described as `church building`, Point Atkinson Lighthouse as `lighthouse`, Book Tower as
`skyscraper`. The name already said that.

Coverage is good where it's needed: of shortlisted POIs with no guide text, **90% of
Vancouver's and 70% of Detroit's have an English Wikipedia article**.

Two API sharp edges:

- `prop=extracts` with `exintro` is **capped at 20 titles per request**.
- **Join by title through `normalized` and `redirects`, never positionally.** Pages come
  back keyed by pageid in no order, and inputs collapse onto one article — 20 titles
  returning 19 pages is normal. Apply `normalized` before `redirects`: a redirect's
  `from` is the *normalised* title, not the raw one.

### Don't pick the "interesting" sentence heuristically

A Wikipedia lead is definitional by convention, so the hook is rarely sentence one.
Across a 16-article sample, an evaluative marker ("renowned for", "known for",
"designated") sat in sentence 1 twice, appeared later 7 times, and was absent 7 times —
and "first sentence containing a marker" selected *"The bridge forms part of Highways 99
and 1A"* for Lions Gate Bridge.

What does work is a **structural** edit, because the exact article title is known:
Wikipedia's house style opens `<Title> is a <definition>`, so stripping that opener
turns "St. Andrew's-Wesley United Church is an affirming church located in the downtown
core" into "An affirming church located in the downtown core". Allow an optional leading
"The", and leave anything that doesn't match the pattern exactly alone so a lead like
"Michigan Central Station (MCS, also known as …) is …" keeps its parenthetical.

## Signals that were measured and rejected

**Commons geotagged-photo density fails.** Counting `list=geosearch` file results within
300 m puts BC Place and Rogers Arena at the 500-result cap, level with Granville Island,
while Stanley Park scores **7** — its pole of inaccessibility is deep in the trees where
nobody stands. It measures how built-up a place is, not whether anything there is worth
a photograph.

**`P1174` visitors-per-year is unusable.** 0.8% coverage (6 of 753 QIDs).

**`P166` award received is unusable as a modern-architecture proxy.** 1.2% coverage
(3 of 247).

## Heritage designation is a proxy for age

`P1435` is the strongest available signal that a building's fabric matters — it is what
separates the Guardian Building from One Wall Centre, both merely `skyscraper` to
Wikidata. But it is structurally unavailable to anything modern:

| Built | Carries `P1435` |
| --- | --- |
| pre-1950 | 51.1% (70/137) |
| 1950–1999 | 6.8% (5/74) |
| 2000+ | **0% (0/34)** |

So any rule that requires a designation silently excludes every modern landmark. There
is no cheap structured substitute — awards are 1.2% covered, and Wikidata frequently
lacks `P84` even when the Wikipedia article names the architect (Vancouver Convention
Centre West: living roof, LEED Platinum, LMN Architects, all in the article body, none
in the item).

## Wikidata P31 class matching: three traps

Using `P31` labels as a lookup key against a hand-written class table:

1. **Match whole phrases, not equality.** Wikidata has no tidy class names — New
   Westminster is not `city`, it is `city in British Columbia`, and so is Port Moody.
   Equality tests fall through to whatever coarser signal is next. Phrase matching also
   makes the table portable: one `city` entry covers every `city in <region>` variant.
2. **Respect word boundaries, and resolve competing tokens inside one label by
   specificity.** `baseball park` contains the whole word `park`; without longest-token
   resolution a ballpark classifies as a park, and `water tower` inherits a
   lighthouse-and-observation-tower prior.
3. **Scope that specificity to one label, not the whole entity.** An entity carries
   several labels describing different aspects, and the wordiest is not the truest.
   Ranking whole entities by token length reads Grouse Mountain as a `ski resort` rather
   than a `mountain`, and the Detroit Institute of Arts as a `performing arts center`
   rather than an `art museum`. Across labels, use declared mode precedence.

Also: keep generic single words out of the table. `association` is a whole word inside
`association football venue`, and having it in an "organisations" list classified a
stadium as an organisation.

## Scoring shape: a prior must never reach the cut

The failure is easy to write and hard to see. With a shortlist cut at 4.0 and an
artwork/museum class prior of 5, every named artwork is auto-included — the shortlist
went to 569 of 2,190, three quarters of it scoring 4.0–4.9 on a class prior and nothing
else, 291 of them artworks including two painted crosswalks.

Priors have to sit **below** the cut so evidence does the lifting. Raising the cut
instead costs real entries while leaving the padding proportionally intact.

The cheapest evidence that separates a public sculpture from street furniture is
**whether anyone created a Wikidata entity for it at all**: Vancouver has 375 artworks
and 18 entities between them. Keep that flat and distinct from a sitelink count —
existing is not the same as being famous. Note the cost, though: gating on Wikidata
presence raises apparent quality sharply while silently dropping real POIs in
under-mapped cities, where coverage runs 10–15% against Vancouver's 15.5%.

## Show what is specific to the place, never the category

The reason line shown under a POI should prefer, in order: the guide's sentence, the
Wikipedia lead, the Wikidata description, and only then a class rationale. A class
sentence is a statement about a *category* read as a statement about a *place* — it is
identical on every POI of its kind and usually sits next to a tag already naming that
category, so it manages to be vacuous and redundant at once. All 17 shortlisted
Vancouver artworks read "Made to be looked at."

With the full chain, the class fallback fires on 2 POIs across two cities.

Wikivoyage and Wikipedia are both CC BY-SA — attribute where their prose is displayed.
