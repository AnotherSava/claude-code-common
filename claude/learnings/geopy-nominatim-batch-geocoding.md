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
