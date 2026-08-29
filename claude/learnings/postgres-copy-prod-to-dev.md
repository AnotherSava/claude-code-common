# Copying a production Postgres into a local dev database

The goal: a dev database holding real data, without ever writing to production and without a half-loaded result
that looks fine. Both containers are reached through `docker exec`, which is where most of the traps are.

## `docker exec` without `-i` reads no stdin — and exits 0

The one that costs the most time, because it fails as a **success**:

```bash
# WRONG: psql gets an empty script, prints nothing, exits 0
ssh host "docker exec pg sh -c 'psql -U \"\$POSTGRES_USER\" -At' <<'SQL'
select count(*) from things;
SQL"
```

No `-i`, so no stdin is attached. `psql` reads an empty script and succeeds, so the command substitution yields an
empty string with **exit status 0** — `set -e` cannot catch it, and a `while read` loop over the result runs its
body zero times and falls through to whatever "all good" line comes next. A verification written this way reports
that it verified something when it read nothing at all.

Two fixes, and you want both:

```bash
docker exec -i pg sh -c '...'                      # attach stdin
[ -n "$out" ] || { echo "read nothing — NOT verified"; exit 1; }   # empty is a failure, not a pass
```

Also assert the *number of things compared*, not just that the loop ran: a truncated read otherwise passes on the
strength of the few rows that did arrive.

Credentials never need to leave the container — `sh -c` lets the container's own environment expand:

```bash
docker exec -i pg sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F"|"'
```

Escape it as `\"\$POSTGRES_USER\"` inside a double-quoted `ssh "..."` argument so the expansion happens in the
container, not locally and not on the remote shell.

## Dump to a file, never stream straight into psql

```bash
ssh host "docker exec pg sh -c 'pg_dump ... --data-only'" > "$DUMP"
grep -q 'PostgreSQL database dump complete' "$DUMP" || { echo "truncated"; exit 1; }
```

A stream piped directly into `psql` that dies halfway — dropped connection, box rebooting — arrives as a *clean
end of input*, so psql commits a half-loaded database and reports success. A file can be checked for the
completion marker `pg_dump` only writes once it has finished. Delete it with a `trap` on EXIT; a data dump of a
real system usually contains personal data.

## `--data-only`, and leave the migration journal alone

```bash
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --schema=public --no-owner --no-privileges
```

Dev is routinely **ahead** of production — a migration is written and tested locally before it is ever deployed —
so copying production's *schema* would undo the very thing being worked on. `--data-only` loads into whatever
`migrate` just built. `--schema=public` also excludes the migration bookkeeping table (Drizzle keeps it in a
`drizzle` schema); importing production's copy would make the tool believe the newest migration had never run.

If production is ever ahead instead, the load fails on a missing column — loudly, and rolled back by the next
section rather than half-applied.

## Empty and load in one transaction

```bash
{ echo "DO \$\$ DECLARE t text; BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
      EXECUTE format('TRUNCATE TABLE public.%I CASCADE', t);
    END LOOP; END \$\$;"
  cat "$DUMP"
} | docker exec -i pg sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q -v ON_ERROR_STOP=1 --single-transaction'
```

`--single-transaction` with `ON_ERROR_STOP=1` means a failure anywhere leaves the dev database exactly as it was,
rather than truncated-and-empty. Truncate by looking tables up rather than from a hardcoded list — a list quietly
stops covering the table added last week, leaving stale rows in that one only.

`pg_dump --data-only` emits tables in foreign-key dependency order, so a straight restore works for an acyclic
schema without deferring constraints.

## Keep the direction impossible to reverse

Production is only ever `pg_dump`ed; the only thing written to is the local container. No flag or environment
variable should be able to swap them. If pushing data the other way is ever needed, that is a different script
with a different name — not an option on this one.
