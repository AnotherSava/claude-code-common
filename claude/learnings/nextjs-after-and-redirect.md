# Next.js `after()` behind a `redirect()`: the destination renders first

`after(callback)` from `next/server` runs the callback once the response is finished. In a server action that
ends with `redirect()`, the response *is* the destination page's render, so that page is rendered and sent
before the callback starts. Anything the callback writes is invisible to the page the user lands on.

Measured on Next 16.3.1 (2026-11-01): an action created an event, called `after(() => runSync(id))` and
redirected to the event page. The sync inserted its `sync_runs` row as `running` as its first statement, yet
the landing page read no run at all and said "Never updated" while the sync was already under way.

## The fix

Split the work so the fact the next page needs is written before the redirect, and only the slow part runs
in `after()`:

```ts
const run = await beginSyncRun(id, 'manual');   // inserts status 'running', awaited
after(() => completeSyncRun(run));              // the long fetch, after the response
redirect(`/events/${slug}`);
```

The page can then read the recorded state and poll (`router.refresh()` on an interval while it says running)
until it finishes.

## What this costs, and what to guard

Once the row is written before the work, anything that can throw between the insert and the work's own
`try` leaves the row stuck at `running`. Move lookups that can fail (an adapter registry, a config parse)
inside the `try` that marks it failed. And because the work runs in the server process, a restart mid-run
also strands the row: close leftover `running` rows once at startup in `instrumentation.ts`, guarded by a
`globalThis` flag, since in development Next re-runs instrumentation on every hot reload while a sync started
before the reload is still running in the same process.
