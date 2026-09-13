# Next.js runs one client's server actions in series — and a background one will block a user's

Next executes server actions from a given client **one at a time**. The second action's request is not merely
queued server-side; the browser does not even put it on the wire until the first resolves. Two actions dispatched
in the same commit run in declaration order, and a long one in front makes every one behind it wait.

This is easy to live with until something *background* becomes a server action. Then a poller, a
stale-while-revalidate refresher, or an on-focus sync is sitting in the same single-file queue as the button the
user just pressed.

## The symptom, and why it misleads

A user action looks slow while **the service it calls is provably idle**. Real case, 2026-09-11: a video player's
negotiation was instrumented and reported `negotiate=8463` ms. The media server's own log showed one request
arriving 150 ms before that leg returned, and nothing at all for the preceding 8.3 seconds — the request had not
been sent yet. Meanwhile an on-view sync, mounted in the root layout and firing on `visibilitychange`, held a
server action for ~9 s.

The pattern of complaint fits exactly and is worth recognising:

- **"It's slow when I come back to it."** The refresher fires on `visibilitychange`, which is the gesture that
  precedes the click. The collision is close to guaranteed on that path.
- **"It's fast when I test it."** A second action right after lands inside the freshness window, so the background
  work is throttled to a no-op. Every check-it-right-now test is in that state.

Chasing the callee is the trap. Timeouts, disk, cold caches and the network all get investigated and all come back
clean, because none of them was ever involved.

## Proving it: time the action inside itself

One number settles it. Time the action end to end **from inside the action** and return that with its result, then
compare against what the client measured:

```ts
// inside the action
const t0 = performance.now()
…
return { ok: true, data, timing: { total: Math.round(performance.now() - t0) } }
```

```ts
// on the client
const started = performance.now()
const r = await myAction(...)
const wall = performance.now() - started
const queued = Math.max(0, wall - r.timing.total)   // clamp: two different clocks
```

- `queued ≈ 0` — the action really is slow; break it into legs.
- `queued ≈ wall` — the action never ran until late. Look for what else was on the queue.

Clamp at zero. The two measurements come from different machines, so a fast call can read a few milliseconds
shorter from the browser than from inside itself, and an unclamped negative reads as a broken instrument.

## The fix: a route handler is not on that queue

Move background work to a route handler and `fetch` it. Same code, same throttle, same JSON back — it simply is not
a server action, so it cannot queue in front of one:

```ts
// app/api/<thing>/route.ts
export const runtime = "nodejs"
export const dynamic = "force-dynamic"
export async function POST(): Promise<Response> { return Response.json(await doTheWork()) }
```

Measured before and after, with a real ~9 s background job deliberately in flight and the user action fired 400 ms
into it: **8463 ms → 407 ms**, and total time-to-first-frame 9440 ms → 1698 ms.

**What this does not buy.** It removes the *queueing*, not the work. If the background job blocks the event loop —
synchronous SQLite writes through better-sqlite3 are the common case — it still occupies the single Node thread
while it runs. Expect a smaller tax, not none, and measure the remainder rather than assuming it away.

## Rules of thumb

- **Never put recurring background work behind a server action.** Actions are for things a user did. A route is for
  everything the page does on its own — polling, revalidating, pinging, reporting.
- **A comment claiming a sync is "non-blocking" is a claim about the sync, not about the queue.** The one in the
  case above said exactly that, and was right about its own throttle and wrong about everything behind it.
- **Order matters even between two of your own effects.** Effects dispatch in declaration order, so an effect that
  fires a secondary lookup declared *above* the one that starts the real work puts a round trip in front of it.
  Moving the declaration is the whole fix.
