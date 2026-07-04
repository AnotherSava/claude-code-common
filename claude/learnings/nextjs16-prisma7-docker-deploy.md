# Next.js 16 + Prisma 7 — production Docker deployment gotchas

Containerizing a Next 16 (App Router) + Prisma 7 (driver-adapter, SQLite) app for a single VPS behind a reverse
proxy. Companion to `nextjs16-prisma7-scaffold.md` (that one is scaffold + the dev migration workflow; this one
is the production image + compose). Observed mid-2026.

## Standalone output — slim runtime, but two things it doesn't copy

`output: "standalone"` in `next.config.ts` makes `next build` emit `.next/standalone/` with a minimal `server.js`
and a traced subset of `node_modules` — deploy it with `node server.js`, no `npm install` in the runtime image.

- **It does NOT copy `public/` or `.next/static/`.** Fold them in after build, or static assets + the client JS
  404 at runtime:
  ```dockerfile
  RUN npm run build \
      && cp -r public .next/standalone/ \
      && cp -r .next/static .next/standalone/.next/
  ```
- **Filesystem-read assets aren't traced.** Tracing follows `import`s only. Anything read from disk at runtime
  (config profiles, templates, a slicer's profile dir) must be `COPY`'d explicitly and pointed at with an env var.
- **`sharp` and `better-sqlite3` are in Next's DEFAULT `serverExternalPackages` list** — so they're externalized
  and their native binaries are traced into standalone automatically. No config needed. Verify with
  `ls .next/standalone/node_modules/{sharp,better-sqlite3}` after a build. (Check the bundled doc
  `serverExternalPackages.md` for the current default list before adding your own.)

## Prisma 7 migrations in a container — run from a stage that still has the schema-engine

The driver-adapter runtime client is **binary-free** (it talks to the DB through `better-sqlite3`/`pg`/etc.), so
the slim standalone runtime has **no** Prisma engine. But `prisma migrate deploy` needs the platform-specific
**schema-engine** binary (under `node_modules/@prisma/engines`, fetched at `npm install` for the build platform).

The clean pattern with multi-stage + compose: keep a full **`builder`** stage (all deps incl. the Prisma CLI +
schema-engine + `tsx` for seeding) and run migrations as a one-shot service that targets it, gating the app on
its success:
```yaml
services:
  migrate:
    build: { context: ../web, target: builder }
    command: sh -c "mkdir -p /data/db && npx prisma migrate deploy"
    env_file: [./app.env]
    volumes: [ /var/lib/app/data:/data ]
  app:
    build: { context: ../web }        # final stage = slim standalone runtime
    depends_on: { migrate: { condition: service_completed_successfully } }
```
- `prisma migrate deploy` is non-interactive + non-destructive — the right migrate command for prod (never
  `migrate dev`/`reset`, which prompt or wipe).
- SQLite: `prisma migrate deploy` creates the DB file but **not its parent dir** — `mkdir -p` it first.
- **Seed AFTER the app/migrate has applied migrations, not before.** `docker compose run --rm migrate npx prisma
  db seed` *overrides* the migrate service's command, so on its own it skips the `mkdir` + `migrate deploy` and
  seeds an empty/absent DB (`SQLITE_CANTOPEN` / "no such table"). Run `compose up` (or the default migrate
  command) first, then seed.
- `next build` itself needs no DB **iff** every DB-backed page is `force-dynamic` (nothing hits Prisma at build
  time). If a page statically renders and reads the DB, the build needs a reachable `DATABASE_URL`.

## Base image — match builder and runtime glibc for native prebuilts

`better-sqlite3` / `sharp` install **prebuilt** binaries matched to the *build* platform's glibc. If the builder's
glibc is newer than the runtime's, the binary fails at runtime (`GLIBC_2.xx not found`). Use the **same** base OS
for builder and runtime (e.g. both `ubuntu:24.04` + Node 24 via NodeSource). This also matters when the runtime
must be a specific distro for another baked-in binary (here: a GUI-linked CLI tool needing that distro's GTK libs).

- `npm ci` installs deterministically from the lockfile regardless of npm minor, so a Corepack round-trip in the
  image is unnecessary (and adds a build-time network failure mode) — the distro's bundled npm is fine for `ci`.

## Reverse proxy (Caddy) — auto-HTTPS + an edge body cap

Caddy as the only publicly-exposed service; the app only `expose`s its port on the compose network
(`reverse_proxy app:3000`, not published to the host). Caddy provisions/renews Let's Encrypt certs for every host
named in the Caddyfile (DNS must resolve to the box first). Redirect alternates to one canonical host. Cap the
body at the edge as a floor under the app's own upload limit:
```
app.example.com {
    encode zstd gzip
    request_body { max_size 110MB }   # valid Caddy v2 syntax; `caddy validate` before reload
    reverse_proxy app:3000
}
alt.example.com { redir https://app.example.com{uri} permanent }
```
With exactly one trusted proxy in front, the trustworthy client IP for rate-limiting is the **rightmost**
`X-Forwarded-For` hop (the one Caddy appends), not the leftmost (client-spoofable).

## Data + backups

- Put the SQLite DB + uploads on a host **bind mount** (`/var/lib/app/data:/data`), not a named volume, so a
  host-level backup script can read them directly without entering the container.
- Back up SQLite with the online snapshot API, never a raw file copy of a live DB:
  `sqlite3 "$DB" ".backup '$STAGE/db.sqlite'"`, then push the stable copy off-box (restic → B2/S3 gives encrypted,
  deduplicated snapshots + `forget --keep-daily/weekly/monthly --prune` retention). Drive it with a systemd timer
  (`Persistent=true` catches a missed run after downtime). **Keep the restic repo password off the box** — without
  it the backups are unrecoverable.
- restic restores files under their **original absolute paths** beneath `--target`, so a DB staged at
  `/var/lib/app/backup-stage/db.sqlite` restores to `$TARGET/var/lib/app/backup-stage/db.sqlite` — reference the
  concrete nested path (don't rely on `**` globstar, which is off in a non-interactive shell).
