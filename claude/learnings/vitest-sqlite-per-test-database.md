# A fresh SQLite database per test under vitest

How to give every test its own migrated SQLite file without paying for the migrations per test, and the three
traps that make the obvious version slow, flaky or leaky. Measured on a Next.js + Prisma 7 +
`@prisma/adapter-better-sqlite3` project with ~25 migrations and ~600 tests on Windows.

## The shape that works

1. **Build one template in vitest's `globalSetup`**, before any worker starts. Each test copies it with
   `copyFileSync` and opens the copy.
2. **Name the template after a hash of the migration SQL** (`test-template-<sha256 prefix>.db`). Every run reuses
   the same file, and a changed migration set gets a new name, so the template never goes stale and nothing has
   to delete it at the end of a run. Sweep templates with other hashes when a new one is built.
3. **Build under a private name and `renameSync` into place**, so two concurrent runs (a commit gate beside
   another agent's test run) never copy a half-written file. If the rename loses the race, delete your copy and
   use the winner's.
4. **Open each per-test copy with `fileMustExist: true`** (better-sqlite3 option, passed through the Prisma adapter's
   config object).

Result on that project: full suite 114 s → 15–19 s, and `maxWorkers`/`hookTimeout` overrides no longer needed.

## The traps

- **Migrations replayed per test** cost ~3 s each alone and far more under default worker counts; the `beforeEach`
  then blows vitest's 10 s `hookTimeout` at random (7, 20, 0, 2 failures across four identical runs, never an
  assertion). Capping workers narrows the spread but does not close it.
- **Building the template inside each worker** is still a cold-start stampede: every worker replays the migrations
  at once on the first run and the first test of each file times out. `globalSetup` is what removes it.
- **`process.once("exit", …)` cleanup does not fire reliably in vitest workers.** A per-worker UUID-named template
  deleted from that handler leaked one file per worker per run — about 600 files over a month.
- **Prisma reconnects lazily after `$disconnect()`.** Work a route starts without awaiting (a fire-and-forget
  dispatch) can run its query after the test's cleanup deleted the file; the adapter reopens the path and
  better-sqlite3 creates it as an empty 0-byte file, which leaks. `fileMustExist: true` makes that late open fail
  instead of creating the file.
