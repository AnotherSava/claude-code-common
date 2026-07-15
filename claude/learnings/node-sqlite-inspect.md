# Inspect a SQLite DB from Node with zero deps (node:sqlite)

Node 22.5+/24 ships a built-in SQLite module — use it to poke a Prisma / `better-sqlite3` dev DB read-only without Prisma Studio, a `sqlite3` binary, or `prisma db execute` (which reads its URL from `prisma.config.ts` and is awkward to point at an arbitrary file).

```bash
node --experimental-sqlite <<'EOF' 2>&1 | grep -v ExperimentalWarning
const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('prisma/dev.db');   // path relative to cwd
console.log(db.prepare("SELECT count(*) n FROM MediaItem").get());        // one row
console.log(db.prepare("SELECT * FROM Foo WHERE x = ?").all(42));         // array
EOF
```

- `.get()` → one row or `undefined`; `.all()` → array; `.run()` → writes (INSERT/UPDATE).
- Read-write by default; for pure inspection just don't run any write statements.
- Safe to run against a DB a dev server already has open — SQLite handles concurrent readers fine.
- Node 24 still gates the module behind `--experimental-sqlite` and prints an `ExperimentalWarning` to stderr; filter the noise with `2>&1 | grep -v ExperimentalWarning` (add `| grep -v "trace-warnings"` too).
- The DB path is resolved against the shell's cwd, so run from the dir where the app's `DATABASE_URL` (`file:./prisma/dev.db`) resolves, or pass an absolute path.
- Great for audit/verification tasks: query row counts, dump specific rows, join tables to check referential integrity — all without touching the app's Prisma client.
