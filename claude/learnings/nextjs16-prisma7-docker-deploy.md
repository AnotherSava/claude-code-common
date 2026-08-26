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
for builder and runtime (e.g. both `ubuntu:24.04` + Node via NodeSource). This also matters when the runtime
must be a specific distro for another baked-in binary (here: a GUI-linked CLI tool needing that distro's GTK libs).

### Never source-build better-sqlite3 12.x — that is what causes the Node 24 abort

**This section previously said "pin Node 22, not 24" and prescribed a forced source build. Both were wrong, and
the source build was the actual cause of the outage. Corrected 2026-08-24 after re-deriving it from Node's own
source.** If you followed the old advice, delete the `--build-from-source` line.

The symptom: `better-sqlite3` 12.x aborts on GC with a fatal `node::RemoveEnvironmentCleanupHook` in
`Statement::~Statement()`, and the container crash-loops. Deceptive as ever — `ExitCode 0`, `OOMKilled=false`,
and a **health probe that stays green while every DB-backed page 502s**. One project logged 17 restarts in 47
minutes before it was spotted.

The mechanism is **not** a tightened assertion. `src/api/hooks.cc` is byte-identical across 22.x and 24.x. What
changed is **`src/node_object_wrap.h` in v24.19.0** (2026-08-03): `node::ObjectWrap`'s constructor gained an
`AddCleanupHook()` call and its destructor a `RemoveCleanupHook()`. So the abort is inherited **from a header at
compile time** by any legacy non-N-API addon deriving from `node::ObjectWrap` — which 12.x's `Statement` does.
Measure it rather than trusting this: `nm -u <addon>.node | grep -c RemoveEnvironmentCleanupHook` is 0 on the
upstream prebuild and 2 on a build against ≥24.19 headers. Open Node regression nodejs/node#65446; fix #65042 is
blocked and in no released 24.x. Versions ≤24.18.1 and 22.x are header-clean, as is 25.9.0 (it predates the change).

**So the fix is to stop compiling it.** The upstream ABI-137 prebuild is built against pre-24.19 headers and is
immune on any Node 24 — verified by executing it: 120,000 churned statements with forced GC on real v24.19.0, no
abort. Delete the rebuild line, keep the base floating, and assert the property on the artifact:

```dockerfile
RUN npm ci \
 && BS3=node_modules/better-sqlite3/build/Release/better_sqlite3.node \
 && if [ ! -f "$BS3" ]; then echo "FATAL: $BS3 not installed" >&2; exit 1; fi \
 && if grep -qa RemoveEnvironmentCleanupHook "$BS3"; then \
      echo "FATAL: built against >=24.19 headers; aborts on GC (nodejs/node#65446)" >&2; exit 1; fi
```

Assert the **property, not the provenance**: `npm ci` runs `prebuild-install || node-gyp rebuild`, so a failed
CDN fetch silently falls back to compiling and the build stays green. Checking the artifact catches that however
it arose. Re-assert on the traced standalone copy in the runtime stage too — that is the binary that ships, and
Next reaches it by a computed `require` path a tracer could drop. (The old CDN-reachability worry that motivated
the source build is real but is now a *loud* build failure, which is the right trade.)

**better-sqlite3 13.x is the N-API rewrite and is immune on any Node — and was still rejected.** It is
behaviourally equivalent (differential-tested through the real adapter: 27/27 adapter and 59/59 driver assertions
byte-identical). It loses on: a **~2.3×–10× resident-memory regression** under the per-query `prepare()` churn a
Prisma driver adapter inherently produces (raw path 47 MB → 607 MB, *rising* to 680 MB after `close()`+`gc()`,
monotonic and invisible to V8 because it is native — reproduced independently, unreported upstream); **npm/cli#9837**,
where npm ships `binding.gyp` and ignores `gypfile:false`, so `npm ci` synthesises `node-gyp rebuild`, making
`python3`+`build-essential` load-bearing and breaking clean installs on Windows (upstream #1516); and the fact
that reaching it needs an `overrides` block that is **silently deletable** — remove it and npm resolves 12.11.x
*nested* under the adapter with exit 0, restoring `ObjectWrap` and the abort with nothing to catch it. Prisma's
adapter still declares `better-sqlite3: ^12.6.0` in every release and dev build through 7.10.0-dev.58.

- `npm ci` installs deterministically from the lockfile regardless of npm minor, so a Corepack round-trip in the
  image is unnecessary (and adds a build-time network failure mode) — the distro's bundled npm is fine for `ci`.

## Naming the runtime env file `<app>.env` defeats both ignore files at once

Giving the rendered production env file a per-app name — `tracker.env`, `storefront.env` — reads well beside a
co-tenant's file, and matches **neither** `.env` nor `.env.*`. Scaffolds ship exactly those two patterns in
`.gitignore` and `.dockerignore`, so a per-app name is silently covered by neither. Two consequences, both severe
and both invisible in review:

1. `env_file:` resolves relative to the compose file, which is usually also the **build context**. The builder
   stage's `COPY . .` therefore bakes the file into the image — and when the same builder image is what the
   `migrate` service runs, `docker compose run --rm migrate cat /app/<app>.env` prints every production secret,
   which also persists in the layer cache.
2. It shows up as an untracked file, so any sweeping `git add` commits production credentials — fatal in a public
   repo.

Fix in both files, and prefer the glob over naming the file so a second app can't reintroduce it:

```gitignore
*.env
!*.env.example
```

Verify rather than assume — `git check-ignore -v <file>` must exit 0, and check the Docker side by matching the
name against `.dockerignore`'s patterns (`fnmatch`), since Docker has no equivalent of `check-ignore`.

## Name the compose project, and give each private repo its own deploy key

Two things that only bite on a box hosting more than one app.

**Compose takes the project name from the directory.** A stack whose compose file lives in `web/` becomes project
`web`, with `web-migrate-1` containers and a `web_data` volume — indistinguishable from the next app's. Fix it in
the file, not with `COMPOSE_PROJECT_NAME` in a shell that only you export:

```yaml
name: tracker
```

Do it before the first real data exists. The project name is *part of the volume name*, so renaming later orphans
the old volume and the stack comes up on an empty one — a silent data loss if you don't notice which volume is
mounted.

**A GitHub deploy key is scoped to one repository.** A box already cloning repo A cannot use A's key for repo B —
`git ls-remote` fails with `ERROR: Repository not found.`, which reads like a typo rather than an authorization
problem. Give each repo its own key and address it with an ssh_config alias:

```
Host github-appb
  HostName github.com
  User git
  IdentityFile ~/.ssh/appb_deploy
  IdentitiesOnly yes
```

`IdentitiesOnly yes` is load-bearing: without it ssh offers every key it has, GitHub accepts the **first valid
one**, and you authenticate as the wrong repository's key. Clone with `git@github-appb:owner/appb.git`; the remote
keeps the alias for later fetches.

Worth noting the trigger: a repo that was public needs no key at all, so **making it private is what breaks an
existing box's access** — the failure arrives later than the change that caused it.

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
