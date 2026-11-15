# PGlite as the Postgres behind database tests

**Serve an in-process PGlite over the Postgres wire protocol and point `DATABASE_URL` at it.** The app's own `pg`
pool then reaches a real Postgres with no Docker, no mock and no test-only hook. Measured 2026-11-14 on Windows,
with `@electric-sql/pglite` 0.5.16, `@electric-sql/pglite-socket` 0.2.19, `pg` 8.23.0, drizzle-orm 0.45.2 and
vitest 4.1.11, first in a Next.js 16 project's test suite and again in a scratch project.

## Why the socket, not the PGlite driver

Drizzle has a `drizzle-orm/pglite` driver, and handing tests a `drizzle(pglite)` instance is the obvious move. It
swaps the client underneath the code under test: the app reaches its database through `drizzle-orm/node-postgres`
and a `pg.Pool` built from `DATABASE_URL`, so a test on the PGlite driver exercises a different session class,
different transaction plumbing and a different type parser. The socket server, `PGLiteSocketServer`, speaks the
Postgres wire protocol on a local port; set `DATABASE_URL` to it and the production `getDb()` path runs untouched.

Use the PGlite driver only for setup, where nothing under test runs. A drizzle-kit `drizzle/` folder goes straight
into the instance with `migrate(drizzle(pglite), { migrationsFolder })` from `drizzle-orm/pglite/migrator`.

## The shape that works

```ts
const pglite = await PGlite.create();                       // in memory
await migrate(drizzle(pglite), { migrationsFolder: MIGRATIONS });
const server = new PGLiteSocketServer({ db: pglite, port: 0, host: '127.0.0.1', maxConnections: 4 });
await server.start();
process.env.DATABASE_URL = `postgres://postgres@${server.getServerConn()}/postgres`;
```

- **Port 0 works.** Before `start()` the server reports `127.0.0.1:0`. Once it resolves, `getServerConn()` returns
  the bound `host:port`.
- **Raise `maxConnections`, which defaults to 1.** A `pg.Pool` opens a second connection the moment two queries
  overlap, and the server turns that one away: the `pg` client's connect fails with `read ECONNRESET`. The server
  does write the words "Too many connections" to the socket, as raw text a Postgres client cannot read. With the
  limit at 4, three overlapping queries ran on three connections.
- **A transaction holds the whole server.** Every connection is multiplexed onto the one PGlite instance through a
  queue that, while a transaction is open, serves only the connection that opened it. That is what keeps a
  transaction made with `db.transaction()` isolated: a query on a second connection waited until the commit and
  then saw the committed row, and after a rollback it did not see the rolled-back one. So a query sent through
  the pool from inside a transaction callback, in place of the `tx` handle, waits on the transaction it is part
  of, and neither finishes.
- **Reset between tests by truncating** every table in `pg_tables where schemaname = 'public'` with `cascade`.
  Drizzle keeps its migration journal in the `drizzle` schema, so the filter leaves it alone.
- **End the app's pool before `server.stop()`.** Stopping the server drops the pool's idle connections, and a pool
  with no `error` listener then ends the process on an `Unhandled 'error' event`, `Connection terminated
  unexpectedly`. Reach the pool through the drizzle instance's `$client`, which is the `pg.Pool` itself, and not
  by copying the app's `globalThis` cache key. Clearing that cache is unnecessary under Vitest's default settings,
  which isolate each test file, so the next file builds its own pool. With `--no-isolate` and one worker, a value
  one file left on `globalThis` was still there for the next.
- **No extensions needed for drizzle defaults.** A `uuid().defaultRandom()` column compiles to
  a `gen_random_uuid()` call, which is core Postgres and present in PGlite.

Cost: in the project this was first measured in, ten migrations plus five tests ran in about 1.7 s for the file.
One instance per test file is cheap enough that the template-database tricks needed for SQLite
(`vitest-sqlite-per-test-database.md`) are not.
