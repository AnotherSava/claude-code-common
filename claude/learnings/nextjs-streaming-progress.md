# Next.js: stream progress for a long server op (NDJSON route + single router.refresh)

For a slow, UI-triggered server operation (bulk refresh, migration, import) you want a real progress bar, not a spinner — and you want to avoid a `revalidatePath` fan-out. Pattern:

1. **Move the work to a Route Handler** that returns a `ReadableStream` of NDJSON — one JSON object per line: `{type:"progress", ...}` while running, then a final `{type:"done", result}` (or `{type:"error", message}`). The worker function takes an **optional** `onProgress` callback that enqueues one line per processed item (optional so a non-UI caller like a cron passes nothing and behaves as before).
   - Compute the total up front (build the work-list, then loop) so the client can size a determinate bar.
   - Emit *before* processing each item if you want to show the in-flight item's name; counts then read as "completed so far".
   - Response headers: `Content-Type: application/x-ndjson`, `Cache-Control: no-store, no-transform`, `X-Accel-Buffering: no` (defeat proxy buffering). Route config: `export const dynamic = "force-dynamic"` and `runtime = "nodejs"` (Prisma / better-sqlite3 need the Node runtime).
   - Gate it and return **JSON** on auth failure, not an HTML redirect a `fetch` would choke on: `try { await requireOwner() } catch { return Response.json({error:"Forbidden"}, {status:403}) }`. (Middleware that redirects `/admin/*` pages does NOT catch `/api/...` — the handler's own guard is the real gate.)
2. **Client** (`"use client"` button) reads the stream: `const r = res.body.getReader()`, a `TextDecoder`, buffer + split on `"\n"`, `JSON.parse` each line, drive the bar from the progress fields. Truncate any in-flight label so a long name can't jitter layout.
3. **On stream end, call `router.refresh()` ONCE** to pull the updated server-rendered summary.

**Why one `router.refresh()` beats multiple `revalidatePath()`:** a `revalidatePath` fan-out (revalidating several routes at the end of a server action) forces on-demand recompilation of each route in dev, which **strobes the Next dev-mode indicator** (the bottom-left status pill) several times per second — it looks broken. It's dev-only (the pill is stripped from the prod build), but confusing. And cookie-dependent (dynamic) pages have no full-route cache to bust anyway, so the fan-out buys nothing: one `router.refresh()` invalidates the client Router Cache and re-renders the current route cleanly; other dynamic routes re-render on next navigation.

Gotcha: that bottom-left flickering pill is **not** your app — grep your source; if nothing renders there, it's Next's dev indicator reacting to recompiles/revalidations.
