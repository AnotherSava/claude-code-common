# Removing a value from a Postgres enum (and the jsonb rows the migration can't reach)

Postgres can add an enum value (`ALTER TYPE … ADD VALUE`) but has no `DROP VALUE`. Removing one means recreating the type, and the generated migration will not survive contact with existing data.

## The generated migration fails on existing rows

`drizzle-kit generate` (and hand-written equivalents) emit roughly: swap the column to `text`, `DROP TYPE`, `CREATE TYPE` without the retired value, swap the column back with a `USING …::new_type` cast. That last cast **fails on every row still holding the retired value** — `invalid input value for enum`. The migration is correct about the *type* and silent about the *data*.

The fix is one statement, and it has to sit in the window where the column is plain `text`:

```sql
ALTER TABLE "activities" ALTER COLUMN "availability" SET DATA TYPE text;
ALTER TABLE "activities" ALTER COLUMN "availability" SET DEFAULT 'unknown'::text;
UPDATE "activities" SET "availability" = 'open' WHERE "availability" = 'limited';  -- add this
DROP TYPE "public"."availability";
CREATE TYPE "public"."availability" AS ENUM('unknown', 'open', 'waitlist', 'sold_out', 'cancelled');
ALTER TABLE "activities" ALTER COLUMN "availability" SET DATA TYPE "public"."availability"
  USING "availability"::"public"."availability";
```

Drop the `DEFAULT` before the type swap and restore it after if the default itself names a value. Always run the whole thing in one transaction — Postgres allows DDL in transactions, so a failed cast rolls the type back rather than leaving the column as `text`.

## The blind spot: jsonb columns keep the retired vocabulary

An enum migration rewrites *columns typed as the enum*. It does nothing to a value stored **inside** a `json`/`jsonb` column, because that value is just a string to Postgres. Anywhere the old vocabulary was captured as data rather than as state survives the migration intact:

- changelog / audit rows storing a `{field: {from, to}}` diff
- event-sourcing payloads, webhook archives, denormalized snapshots
- any "what did it look like at the time" record

Symptom: a value you deleted from the schema keeps appearing in the UI, long after `SELECT count(*) … WHERE col = 'retired'` returns zero. The rendering code is innocent — it prints what the JSON holds.

Find them with a text cast, which reaches inside the document:

```sql
SELECT kind, count(*) FROM activity_changes
WHERE field_diff::text ILIKE '%limited%' GROUP BY kind;
```

Rewrite in place with `jsonb_set` (note the value argument is JSON, so a string needs its own quotes):

```sql
UPDATE activity_changes SET field_diff = jsonb_set(field_diff, '{availability,from}', '"open"')
WHERE field_diff->'availability'->>'from' = 'limited';
```

## Not every surviving row should be rewritten

Mapping the retired value to its replacement is right only where the record stays true. Sort them by transition before touching anything:

- `sold_out → limited` under a vocabulary where `limited` folded into `open` becomes `sold_out → open` — still a real event, rewrite it.
- `limited → open` becomes `open → open` — a transition that *did not happen* under the new vocabulary. It would never be written today, so **delete it**; rewriting produces a row asserting a change to nothing.

Guard the whole cleanup with post-conditions checked before `COMMIT`, so a mistake rolls back instead of shipping:

```js
await c.query('BEGIN');
// … deletes and updates …
const left = await c.query("SELECT count(*)::int AS n FROM activity_changes WHERE field_diff::text ILIKE '%limited%'");
const noop = await c.query("SELECT count(*)::int AS n FROM activity_changes WHERE field_diff->'availability'->>'from' = field_diff->'availability'->>'to'");
if (left.rows[0].n !== 0 || noop.rows[0].n !== 0) throw new Error('post-conditions not met');
await c.query('COMMIT');
```

## Do this as a throwaway, not a migration

Rewriting historical records is a one-time correction of accumulated data, not a schema change every environment must replay. A migration file makes it permanent project surface for a single run. Run it as a script against the databases that actually hold the rows, and keep only the schema change in the migration.

Related: counts denormalized onto a parent row (a sync run's `changed_count`) do **not** follow rows you delete. Decide deliberately whether the tally is an index into the child rows (fix it) or a record of what a past run did (leave it, and say so).
