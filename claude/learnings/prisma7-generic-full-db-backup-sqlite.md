# Prisma 7 + better-sqlite3: generic full-database backup / restore

How to snapshot and restore an *entire* database through Prisma without hand-listing tables or columns — so a model/column added later is captured automatically. Verified 2026-07-25 on Prisma 7.8 with `@prisma/adapter-better-sqlite3`. Companion to `nextjs16-prisma7-scaffold.md`, `nextjs16-prisma7-docker-deploy.md`, `prisma-migration-checksum-drift.md`.

## The problem it solves

A backup that hand-lists each model's columns (a per-model `findMany` + a zod schema + a per-row `create`) silently drops any model or column added to the schema *after* the backup code was written. The fix is to enumerate the schema generically.

## Key verified facts (each probed against a throwaway DB copy)

1. **`Prisma.ModelName` exists as a runtime const map** of every model name (PascalCase), even though this client build has **no `Prisma.dmmf`**. `Object.values(Prisma.ModelName)` is the drift-proof table list. The client delegate is camelCase: `m[0].toLowerCase() + m.slice(1)` (`"OrderItem"` → `orderItem`).
2. **`createMany` accepts ISO date *strings* for `DateTime` columns** and reads them back as `Date`. So a JSON round-trip (Date → ISO string on `JSON.stringify`) needs **no coercion** on the way back in — pass the parsed rows straight to `createMany`.
3. **`createMany` preserves an explicitly-provided `@default(now())` `createdAt` AND `@updatedAt`.** Passing `updatedAt` in the data is honored on create (not overwritten with now()), so a snapshot round-trips **losslessly** — every timestamp verbatim. (Only *update* operations force `@updatedAt`; create honors an explicit value.)
4. **`PRAGMA defer_foreign_keys=ON` works inside a Prisma interactive transaction** on the better-sqlite3 adapter: `await tx.$executeRawUnsafe("PRAGMA defer_foreign_keys=ON")` defers FK enforcement to commit. So restore can `deleteMany` every table then `createMany` every table **in any order** — a child can be inserted before its parent; the whole graph validates once, atomically, at commit. No topological ordering of inserts needed. (The PRAGMA is per-connection/transaction and must be re-issued inside each tx.)
5. `findMany()` with **no `include`** returns exactly the scalar columns (relation *scalars* like `orderId` included, relation *objects* excluded) — which is exactly what `createMany` takes back.

## The recipe

```ts
import { Prisma, type PrismaClient } from "@/generated/prisma/client";

const MODEL_NAMES = Object.values(Prisma.ModelName);
type Row = Record<string, unknown>;
type Delegate = { findMany: () => Promise<Row[]>; deleteMany: () => Promise<unknown>; createMany: (a: { data: Row[] }) => Promise<unknown> };
// The payload is generic by design, so per-model input types don't apply — cast once.
const delegate = (client: unknown, model: string): Delegate =>
  (client as Record<string, Delegate>)[model[0].toLowerCase() + model.slice(1)];

async function exportData(prisma: PrismaClient) {
  const tables: Record<string, Row[]> = {};
  for (const m of MODEL_NAMES) tables[m] = await delegate(prisma, m).findMany();
  return { version: 5, exportedAt: new Date().toISOString(), tables };
}

async function importData(payload: { tables: Record<string, Row[]> }, prisma: PrismaClient) {
  await prisma.$transaction(async (tx) => {
    await tx.$executeRawUnsafe("PRAGMA defer_foreign_keys=ON");
    for (const m of MODEL_NAMES) await delegate(tx, m).deleteMany();
    for (const m of MODEL_NAMES) {
      const rows = payload.tables[m];
      if (rows?.length) await delegate(tx, m).createMany({ data: rows });
    }
  }, { timeout: 60_000 }); // interactive-tx default is 5s; a full restore can exceed it
}
```

Envelope validation stays generic — validate the shape, not each column (Prisma's `createMany` rejects an unknown column on write): `z.object({ version: z.literal(5), exportedAt: z.string().optional(), tables: z.record(z.string(), z.array(z.record(z.string(), z.unknown()))) })`.

## Self-contained round-trip test harness (no reliance on the dev DB)

Stand up a throwaway migrated SQLite file with `prisma db push`, then point a real client at it:

- **Prisma 7 removed `--skip-generate` from `db push`** (it no longer regenerates the client anyway) and added **`--url`** to override the datasource. Use it instead of an env var:
  ```ts
  execSync(`npx prisma db push --url "file:${dbFile.split(path.sep).join("/")}" --accept-data-loss`, { cwd, stdio: "ignore" });
  const prisma = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: `file:${...}` }) });
  ```
- Use forward slashes in the `file:` URL even on Windows (native `os.tmpdir()` path). A Git Bash `/tmp/...` path gets mis-translated by the Windows Prisma binary — build the path with Node's `os.tmpdir()` + `mkdtempSync`, not a bash `mktemp`.
- The datasource block can omit `url` when a `prisma.config.ts` supplies `datasource: { url: process.env.DATABASE_URL }`; `db push --url` overrides it regardless.
- Round-trip assertion: seed → `export` → `JSON.parse(JSON.stringify(...))` (exercise the real serialize+validate path) → `clearData` → `importData` → `export` again → `expect(second.tables).toEqual(first.tables)`. `toEqual` compares `Date`s by value, and rows come back in rowid (= insertion) order on both sides, so it's order-stable without an explicit `orderBy`.

## Gotchas

- Any value your code used to *regenerate* on import (e.g. a `@unique` capability token that was minted per-row) is now **carried verbatim** in the snapshot — correct for a faithful restore, and the `@unique` can't collide because every table is cleared first. But any *code path that seeds data* (sample/demo builders) must now supply that column itself, since import no longer synthesizes it.
- Rest-sibling destructuring is the clean way to drop relation arrays while keeping every scalar column without hand-listing (`const { items, events, ...row } = order`). ESLint `@typescript-eslint/no-unused-vars` flags the siblings — set `ignoreRestSiblings: true` (it only relaxes the rule).
