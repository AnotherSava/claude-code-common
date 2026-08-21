# Postgres in an alpine image can have no DST rules

`postgres:17-alpine` (observed; other alpine tags likely behave the same) resolves named IANA zones to a
**fixed offset with no daylight-saving transitions**. It does not error — it answers confidently and wrongly.

Observed on a `postgres:17-alpine` container, for a Vancouver-based dataset:

```sql
SELECT (timestamptz '2026-11-05 18:00:00+00' AT TIME ZONE 'America/Vancouver');  -- 2026-11-05 11:00:00
SELECT (timestamptz '2026-08-20 18:00:00+00' AT TIME ZONE 'America/Vancouver');  -- 2026-08-20 11:00:00
SELECT (timestamptz '2026-12-20 18:00:00+00' AT TIME ZONE 'America/Vancouver');  -- 2026-12-20 11:00:00
```

August, November and December all come back UTC−7. November and December should be UTC−8 (PST); DST ends on the
first Sunday of November. The catalog agrees with itself about being wrong:

```sql
SELECT name, abbrev, utc_offset, is_dst FROM pg_timezone_names
WHERE name IN ('America/Vancouver', 'America/Los_Angeles');
-- both: abbrev PDT, utc_offset -07:00, is_dst true  (regardless of the current date)
```

Node on the same machine is correct — `DateTime.fromISO('2026-11-05T10:00', {zone:'America/Vancouver'})`
resolves to `-08:00`/PST, and `Intl.DateTimeFormat` agrees. So a disagreement between your app and your database
about the same instant is the signal.

The likely cause is the alpine image shipping no (or a stub) `tzdata` package, so Postgres falls back to a
single offset per zone. That cause is inferred from the symptom, not confirmed by inspecting the image.

## What to do

**Check before trusting timezone SQL against a containerised Postgres:**

```sql
SELECT (timestamptz '2026-08-20 18:00:00+00' AT TIME ZONE 'America/Vancouver')::text AS summer,
       (timestamptz '2026-12-20 18:00:00+00' AT TIME ZONE 'America/Vancouver')::text AS winter;
```

Equal offsets means the zone table is flat and every `AT TIME ZONE`, `date_trunc(... AT TIME ZONE ...)` and
timezone-aware `to_char` in that database is untrustworthy across a DST boundary.

Fixes, in order of preference:

1. **Do zone conversion in the application**, not in SQL. Store `timestamptz` (absolute instants, which are
   unaffected — the bad data never reaches the column) and render with a real zone library. An app that never
   writes `AT TIME ZONE` is immune to this, and the immunity is worth having on its own merits.
2. Install tzdata in the image (`apk add --no-cache tzdata`) or switch to the Debian-based `postgres:17` tag.

The trap is that this only bites at *verification* time: ad-hoc "let me just group these by day in SQL" queries
produce plausible, off-by-one-hour answers about data that is actually stored correctly, and it reads as an
application bug. Confirm which side is wrong before changing any code.
