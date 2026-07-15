# Fixing Prisma "migration modified after applied" without a data-losing reset

## Symptom

`prisma migrate dev` refuses to apply a new migration and wants to reset the database:

```
The migration `20260710182401_add_plex_rating_key` was modified after it was applied.
We need to reset the SQLite database "dev.db" ...
You may use prisma migrate reset to drop the development database. All data will be lost.
```

`migrate reset` / letting `migrate dev` reset would **wipe the dev database**. Don't. This is almost always a
harmless *checksum drift*, not a real schema mismatch.

## Cause

Prisma records, per applied migration, a SHA-256 checksum of the `migration.sql` file in the `_prisma_migrations`
table. If someone edits an already-applied `migration.sql` afterwards (even just a comment), the file's hash no
longer matches the stored checksum, and `migrate dev` treats it as "modified after applied" and demands a reset —
even though the actual schema is already correct (the DDL ran when it was first applied).

## Diagnose (confirm it's only a checksum drift)

No `sqlite3` CLI on Windows — inspect via `node` + `better-sqlite3` (a Prisma/SQLite project already has it):

```js
// node <<'EOF'  (run from the dir holding prisma/dev.db)
const Database = require('better-sqlite3');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const db = new Database('prisma/dev.db', { readonly: true });
for (const r of db.prepare('SELECT migration_name, checksum FROM _prisma_migrations').all()) {
  const buf = fs.readFileSync(path.join('prisma/migrations', r.migration_name, 'migration.sql'));
  const computed = crypto.createHash('sha256').update(buf).digest('hex');
  console.log(computed === r.checksum ? 'OK   ' : 'DRIFT', r.migration_name);
}
db.close();
// EOF
```

Also verify the migration's DDL is actually present in the schema (e.g. `PRAGMA table_info('SomeTable')` shows the
added column). If the column exists and only the checksum differs, it's pure drift — safe to reconcile.

## Fix (non-destructive)

Back up `dev.db` first, then update the drifted row's checksum to the current file's hash:

```js
// node <<'EOF'
const Database = require('better-sqlite3');
const db = new Database('prisma/dev.db'); // writable
const info = db.prepare(
  'UPDATE _prisma_migrations SET checksum = ? WHERE migration_name = ? AND checksum = ?'
).run(NEW_FILE_SHA256, MIGRATION_NAME, OLD_RECORDED_CHECKSUM);
console.log('rows updated:', info.changes); // expect 1
db.close();
// EOF
```

Then re-run `prisma migrate dev --name <your_new_migration>` — it now sees a clean history and applies the new
migration normally, no reset.

## Notes

- The committed `migration.sql` (matching git HEAD) is the source of truth; reconcile the DB's recorded checksum to
  it, not the reverse.
- WAL mode: writing via a second `better-sqlite3` connection while `next dev` holds the DB open works fine — the
  committed UPDATE is visible to the server's next read.
- Prevention: never edit a `migration.sql` after it's been applied. If you must, expect to reconcile the checksum on
  every machine that already applied the old version.
- Related: `node-sqlite-inspect` (the general node+better-sqlite3 inspection technique this builds on).
