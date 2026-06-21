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
