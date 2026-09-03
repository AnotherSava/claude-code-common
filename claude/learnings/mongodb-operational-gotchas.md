# MongoDB: constraints, memory, and backups

Things that bite when a document store replaces a relational one. Verified August 2026 against MongoDB 8 in
Docker.

## `partialFilterExpression` cannot express `$ne`

A partial unique index is how you say "at most one *live* row per key" — the document-store equivalent of a
Postgres `CREATE UNIQUE INDEX … WHERE status <> 'superseded'`. Mongo supports partial indexes, but the filter
accepts only equality, `$exists`, `$type`, `$gt/$gte/$lt/$lte` and `$and`. **Not `$ne`, not `$in`, not `$nin`.**

So this is rejected:

```js
{ unique: true, partialFilterExpression: { status: { $ne: 'superseded' } } }   // ✗
```

Materialise the predicate as a field the writer sets instead:

```js
await bookings.createIndex(
  { provider: 1, confirmationCode: 1 },
  { unique: true, partialFilterExpression: { live: true, confirmationCode: { $type: 'string' } } },
);
```

Two consequences worth designing around. The writer must set `live` and `status` **together and nowhere else**,
or they drift and the constraint quietly stops meaning what it says. And the `$type: 'string'` clause is doing
the work a Postgres `WHERE col IS NOT NULL` would: without it every document lacking the field collides on
`null`.

Verify it is actually enforced rather than assuming — insert a genuine duplicate and confirm `E11000`. An index
that was silently not created looks exactly like one that was.

## There is no migration step, and that is a trap as much as a convenience

Nothing needs a schema migration, so it is tempting to conclude nothing needs a deploy step at all. But
**indexes are not shape, they are constraints** — and a unique index is the only thing standing between you and
duplicate data. Create them idempotently at server start (`createIndex` is safe to re-run) rather than in a
one-off script nobody runs on a fresh database.

The consequence to write down somewhere: a database that has never had the app start against it has **no
constraints on it at all**.

## WiredTiger will take half the machine

The cache defaults to **50% of RAM minus 1 GB**. On an 8 GB box that is ~3.4 GB claimed by one container. On a
host shared with other tenants — especially any with a latency budget — cap it explicitly:

```yaml
command: ["--wiredTigerCacheSizeGB", "0.25", "--bind_ip", "0.0.0.0"]
```

A few thousand documents need nothing like the default. This is the single most important line in a
shared-host compose file, and it is invisible until a neighbour starts swapping.

## Backups: `mongodump` from inside the container

Same shape as any database backup, with one specific:

```sh
docker exec -i "$DB_CONTAINER" mongodump --uri "$MONGODB_URI" --archive --gzip > dump.archive.gz.partial
mv dump.archive.gz.partial dump.archive.gz
```

- **Run it inside the container.** The tool ships with the image, so its version matches the server by
  construction, and nothing Mongo-shaped has to be installed on the host.
- **`--archive` writes a single file** rather than a directory tree, which restic and friends deduplicate far
  better across nightly runs. `--gzip` on top, because BSON compresses well.
- **Write to `.partial` and move on success.** A dump that dies halfway must not leave a truncated archive for
  the backup tool to snapshot as though it were good.
- Restore with `mongorestore --archive --gzip --drop`, and verify with `--dryRun` first — it parses the archive
  without writing anything.

### `--drop` drops the archive's collections, not the database

Worth knowing before pointing a restore at a live database, because it is the difference between a targeted
replace and a wipe: `--drop` drops each collection **the archive contains**, immediately before restoring that
collection. Anything else in the target database is untouched. So a dump of three collections restored over a
database holding five leaves the other two exactly as they were — a safety property you can lean on, and
equally a gap if you assumed the target would end up identical.

That makes dump-and-restore a reasonable way to push one environment's data onto another, not only a backup
path. Two conditions: run dump and restore **inside their respective containers**, so each tool's version
matches its own server, and confirm the two server versions agree before starting. Scope it with
`--nsInclude 'mydb.*'`, and snapshot the target immediately before and after rather than trusting the nightly
timer to have run recently.

**Verify with a content fingerprint, not document counts.** Counts match while contents differ, so they cannot
distinguish a correct restore from a coincidence. Hash a sorted projection of something identifying and compare
both sides:

```js
const codes = db.bookings.find({}, {confirmationCode: 1}).toArray().map(b => b.confirmationCode || '').sort();
print(require('crypto').createHash('sha256').update(codes.join('|')).digest('hex').slice(0, 16));
```

Indexes travel with the archive — `mongorestore` rebuilds them from the dump's metadata, unique partial indexes
included — so the constraint the schema depends on is restored with the data rather than left to whenever the
application next boots.

## Driver notes

- Cache the `MongoClient` on `globalThis` across hot reloads, the same way a Postgres pool is cached. The
  driver pools internally and is designed to be a long-lived singleton; a fresh client per reload opens a fresh
  pool until the server refuses more.
- Put the database name in the URI path so it is configured in one place rather than two.
- `db.command({ ping: 1 })` is the health check. It proves the server accepts a command, which is what a
  readiness probe wants — not that a collection exists.
