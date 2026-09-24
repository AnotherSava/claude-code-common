# `instrumentation.ts` does not share module state with your routes

A process-wide singleton created in Next's startup hook is invisible to the route handlers that need it. The hook runs, the constructor runs, the log line prints — and a route reading the same module-level variable sees `null`. Nothing errors, so the conclusion on offer is that the thing never started, which sends you to debug the wrong half.

Measured 2026-09-23 on Next 16 (App Router, standalone output), on a WebSocket client created at startup and reported by `/api/health`.

## What is actually happening

Next bundles `instrumentation.ts` as its own entry. Route handlers are bundled separately. A module imported by both therefore has **two instances** in one process, each with its own copy of every module-level binding:

```ts
// lib/notify.ts
let subscriber: Subscriber | null = null;          // one of these per bundle, not per process

export function start() { subscriber ??= new Subscriber(); subscriber.start(); return true; }
export function status() { return subscriber?.status() ?? null; }   // always null in the route's copy
```

The startup hook calls `start()` and its copy is populated. `/api/health` calls `status()` on a *different* copy and gets `null`. Both are telling the truth about the module they can see.

**The symptom is the tell:** a startup log that says it worked, next to a reader that says it did not, with the underlying resource demonstrably alive. Do not go looking for a failed connection.

## The fix

Put the instance somewhere the realm shares. `Symbol.for` takes a key from the cross-realm registry, so every copy of the module resolves the same slot:

```ts
const HOLDER = Symbol.for('app.mail.subscriber');
type Holder = { [HOLDER]?: Subscriber };

export function start(): boolean {
  const holder = globalThis as Holder;
  holder[HOLDER] ??= new Subscriber(config);
  holder[HOLDER].start();
  return true;
}

export function status() { return (globalThis as Holder)[HOLDER]?.status() ?? null; }
```

A plain string property on `globalThis` works too; the symbol only keeps it from colliding with a library doing the same thing.

## Where else this bites

Anything long-lived started from the hook and observed from a request: a message-queue consumer, a metrics registry, a cache warmer, a scheduler handle. The same reasoning applies to the well-known `globalThis` database-client pattern — that one is usually explained as surviving dev hot-reload, and this is the second, quieter reason it is written that way.

**Testing will not catch it.** Unit tests import one copy of the module, so a module-level singleton passes everything. The only honest check is the deployed process: read the value back from the route that consumes it, not from the log line that sets it.

## Related

- `nextjs-tailwind4-css-gotchas.md` — the other class of "it ran but had no effect" in this stack.
