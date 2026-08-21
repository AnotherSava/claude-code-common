# Drizzle + Next.js: caching the db handle serves a stale schema

## Symptom

You add a column to the Drizzle schema, run the migration, and the new column shows up on **some** pages and
not others — in the same dev server, reading the same row.

Concretely: a list page rendered the new `venue` column fine, while a detail page for the same record showed it
as absent. Both read the same table. No error, no warning; the two pages simply disagreed about what the row
contained.

## Cause

The usual Next.js dev-server pattern memoizes something on `globalThis` so hot reload doesn't leak connections:

```ts
// The problem
const globalForDb = globalThis as unknown as { pool?: Pool; db?: NodePgDatabase<typeof schema> };

export function getDb() {
  if (globalForDb.db) return globalForDb.db;          // ← survives every hot reload
  const pool = globalForDb.pool ?? new Pool({ connectionString });
  const db = drizzle(pool, { schema });                // ← schema snapshot taken ONCE
  globalForDb.pool = pool;
  globalForDb.db = db;
  return db;
}
```

Drizzle's two query styles resolve columns at different times:

| Style | Columns resolved | Sees a new column after hot reload? |
|---|---|---|
| `db.select().from(table)` | per call, from the freshly imported table object | **yes** |
| `db.query.table.findFirst()` | from the `schema` snapshot passed to `drizzle()` | **no** |

The relational query API builds its column map when `drizzle()` is constructed. Cache that instance across
reloads and `db.query.*` keeps serving the schema as it was at first construction, while `db.select()` picks up
the change immediately. Hence two call sites disagreeing.

## Fix

Cache the **pool** — which is the only thing that actually needs to survive a reload — and rebuild the drizzle
handle each time. Constructing it is cheap; opening connections is not.

```ts
const globalForDb = globalThis as unknown as { pool?: Pool };

export function getDb(): NodePgDatabase<typeof schema> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) throw new Error('DATABASE_URL is not set.');

  const pool = globalForDb.pool ?? new Pool({ connectionString });
  globalForDb.pool = pool;
  return drizzle(pool, { schema });   // fresh schema every call
}
```

## Notes

- Dev-only. A production process is created once with one schema, so it never diverges — which is exactly why
  this is confusing to diagnose: it reproduces only in the environment where you add columns.
- The same shape applies to any ORM that snapshots a schema at client-construction time; the trap is the
  `globalThis` cache holding the *client* rather than the *connection*.
- Resolve the db handle lazily inside a function rather than at module scope. `next build` evaluates every
  module while prerendering, and a module-level `throw` on a missing `DATABASE_URL` fails a build that was
  never going to connect to anything.
