# Verifying a pg_dump before and while restoring it

A truncated plain-format `pg_dump` restores **silently and successfully**. Every guard that looks like it
would catch this does not, and the one check that works is not the one people reach for.

## The trap

The usual careful restore is:

```
psql -U <role> -d <db> -v ON_ERROR_STOP=1 --single-transaction < dump.sql
```

Those two flags are real and worth setting — but they catch a **SQL error**, not a short file. Measured on
PostgreSQL 17 with a dump cut partway through a `COPY` block: psql restored every table in the dump, committed,
and exited **0**. Nothing in the output said anything was missing.

The reason is `COPY`'s stream framing. In a plain dump each table's rows follow the `COPY … FROM stdin;`
statement as raw lines, terminated by a `\.` line. psql feeds lines to the server until it sees that terminator
**or reaches EOF**, and EOF is not an error — the copy simply ends with however many rows arrived. So a file
cut mid-stream produces a short table rather than a failed statement, and from there the transaction commits
normally.

What this means in practice: `ON_ERROR_STOP` + `--single-transaction` protect you from a *malformed* dump and
from a half-applied restore, and not at all from an *incomplete* one.

## The check that works

A complete plain dump contains the line `-- PostgreSQL database dump complete`. Test for it
position-independently, before loading:

```
grep -c 'PostgreSQL database dump complete' dump.sql     # must print 1
```

**Do not use `tail`.** It is the obvious instrument and it fails on current versions: pg_dump writes
`\unrestrict <token>` lines *after* the completion marker, which leaves the marker four lines from the end.
Measured 2026-10-08 on pg_dump 15.19, 16.15 and 17.11 — all three carry the trailer, so an older major is not
exempt. A `tail -n 3` found nothing on any of those complete files, the same answer it gives on a truncated
one, which is the worst possible failure for a check whose whole job is telling those apart.

Put the grep **before** the load, not after. Once the load has run there is nothing to abort.

## The restore sequence, and one assumption worth knowing is safe

A dump taken with `pg_dump --no-owner` and without `--clean` emits `CREATE` and no `DROP`, so it needs an
empty database:

```
docker compose stop <app-that-holds-connections>
docker exec <pg-container> dropdb -U <role> --force <db>
docker exec <pg-container> createdb -U <role> -O <role> <db>
docker exec -i <pg-container> psql -U <role> -d <db> -v ON_ERROR_STOP=1 --single-transaction < dump.sql
docker compose up -d <app>
```

- `dropdb --force` disconnects stragglers; it needs PostgreSQL **13+**.
- `dropdb` and `createdb` connect through a *different* database than the one being dropped, which in the
  official image is `postgres`. That database exists **even when `POSTGRES_DB` names something else** — initdb
  always creates it — so the sequence works on a container whose only application database is the one being
  replaced. Verified rather than assumed, because the whole sequence fails at step one if it is not there.
- Stopping the application first matters: `--force` will disconnect it, but a connection pool that reconnects
  mid-load repopulates nothing and can block the drop on the next attempt.

## Drill it against a throwaway, not against the live database

The sequence above destroys a database, so exercising it on the real one is not a drill. Run it against a
disposable container on the **same image pin** as production, feeding it a real dump:

```
docker run -d --name restore-drill -e POSTGRES_USER=<role> -e POSTGRES_DB=<db> \
  -e POSTGRES_PASSWORD=<throwaway> postgres:<same-pin-as-prod>
# wait for pg_isready, run the sequence above against restore-drill, compare row counts
docker kill restore-drill && docker rm -v restore-drill
```

Compare counts against the live database rather than only checking that the load exited 0 — that comparison is
what would have caught the truncation case above, and it is the reason to drill with a real dump rather than a
synthetic one.

Two things a drill like this is uniquely good at finding, both of which it found: a guard that does not guard
what its comment claims, and a check written against a file format that has since grown a trailer.

## Related

- `postgres-two-servers-one-data-directory.md` — taking a dump as the available *integrity* check when page
  checksums are off. That is the read side; this file is the write-it-back side.
- `copy-prod-db-to-dev.md` — the same completion-marker check inside a direction-safe copy procedure, which
  empties the target with `TRUNCATE` and loads `--data-only` instead of dropping the database.
