# Batch geocoding with geopy + Nominatim (esp. on Windows)

## Windows: non-ASCII print crashes the run
Python stdout on Windows uses the console's legacy code page (e.g. cp1251), which
can't encode names like "Plzeň" → UnicodeEncodeError. One progress print() of a
city name kills the whole run. Fix at top of script:

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

## Persist the cache incrementally
At 1 req/sec (Nominatim policy), a few-hundred-item run that only writes at the end
loses everything on a crash near the end. Write the cache after EACH new geocode so
crashes/blips never lose progress and re-runs resume.

## Transient failures
Sporadic SSL handshake / GeocoderTimedOut. Use timeout + retries:
`Nominatim(user_agent=..., timeout=10)` + `RateLimiter(..., max_retries=3,
error_wait_seconds=5)`. RateLimiter retries transparently.

## Names that confuse it
- Strip parenthetical suffixes from BOTH name and region ("Bruges (Brugge)"→"Bruges";
  region "Saint Petersburg (federal city)"→"Saint Petersburg"); keep originals for display.
- Composite frazione names ("Ripa-Pozzi-Querceta-Ponterosso") won't resolve — fall
  back to the main settlement or hand-add coords.
- user_agent is mandatory (descriptive/identifying) per Nominatim policy.

## Reject a result that resolved only to a city — a failed lookup returns the centre

When a street lookup fails, Nominatim does not return nothing. It returns the enclosing city, suburb or
administrative area, with a perfectly well-formed lat/lon at its centroid. Stored, that is indistinguishable
from a precise hit and reads as exact everywhere downstream.

Two guards, and the second is the one that matters:

```python
TOO_COARSE = {"city", "town", "village", "administrative", "suburb",
              "neighbourhood", "county", "state", "postcode"}

ok = (expected_city.lower() in hit["display_name"].lower()
      and hit["type"] not in TOO_COARSE)          # jsonv2: `type`, alongside `category`
```

The first guard (is it in the city we expected) catches a confident answer in the wrong town. The second catches
a confident answer that is only *the town*. Without it a batch reports 100% success and quietly pins a row of
addresses to their city centres.

**Leave a rejected row without coordinates rather than storing the coarse hit.** Absent coordinates can be
detected and reported; a centroid cannot be distinguished from a real one later, and it fails at the moment
somebody is relying on it.

The wider point, independent of the geocoder: a value a machine guessed and a value a human checked must not
end up in the same field with nothing to tell them apart. Either keep provenance alongside it, or do not write
the guess at all.

## A precise hit on the wrong object passes both guards

Expand a code or a booking system's shorthand to the official name before the lookup, and leave the row for a
person where you cannot. The two guards above reject a coarse answer and an empty one; neither rejects a
precise answer about something else. `BCN-SANTS, Barcelona, ES` returns a restaurant 200 m from the station —
`type=restaurant`, in the expected city, well-formed coordinates — and nothing in the response separates it
from a correct hit.

Measured 2026-10-11 over five real confirmation addresses: two usable (`type=platform`, `type=train_station`),
one city boundary the coarse guard caught, one with no hit at all, and that restaurant. Four of the five
returned something, so a batch counting responses reports 80% and ships one silently wrong coordinate.

The strings that cause it are the ones a booking system writes rather than a person: `BCN-SANTS`,
`ALICANTE/AL`, `ЧЕРЕПОВЕЦ 1`. A geocoder has nothing to match them against and answers with whatever is
nearest the words it does recognise.

## Wikidata answers an official name, not the string a document carries

Reach it with `wbsearchentities` for the item and `Special:EntityData/<qid>.json` for its claims; `P625` holds
the coordinate. It settles the pair a geocoder cannot — one place written in two scripts — because the item
carries both labels: `Ярославль-Главный` resolves to Q1967106 at 57.62558,39.83528, labelled that in `ru` and
`Yaroslavl railway station` in `en`, so two documents naming one station reconcile through the item rather
than through a transliteration table.

It answers the official name and nothing else. `Череповец 1` and `BCN-SANTS` return no item, which is the same
wall the geocoder hits from the other side: the limit is the input string, not the dataset.
