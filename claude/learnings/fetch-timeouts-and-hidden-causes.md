# fetch timeouts: the body is not covered, and the real error is on `cause`

Two defects that travel together in almost every hand-rolled `fetch` wrapper. Both measured 2026-09-06
against Node 24 / undici, after a day-long media-server outage produced a log line that said nothing and
a timeout that could not have fired.

## 1. Clearing the timer when the Response arrives leaves the body unbounded

The usual shape, and the bug:

```ts
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), timeoutMs);
let res: Response;
try {
  res = await fetch(url, { signal: controller.signal });
} finally {
  clearTimeout(timer);          // <- the deadline ends HERE
}
return res;                      // caller then does `await res.json()`, untimed
```

`fetch` resolves as soon as the response **headers** arrive. The body is streamed afterwards, and by then
the timer is cancelled, so a server that answers `200` and then stalls mid-body hangs forever with
nothing to abort it. This is worst exactly where it matters most: paged API reads, where the bodies are
the large ones.

The fix is to keep one deadline across the whole exchange, which means the body read has to happen inside
the timed region. Pass the read in rather than returning the `Response`:

```ts
private async exchange<T>(method: string, path: string, body: unknown,
                          read: (res: Response) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error(`no answer within ${ms}ms (${method} ${url})`)), ms);
  try {
    const res = await fetch(url, { method, signal: controller.signal, ... });
    if (!res.ok) throw new ServerError(`${res.status} on ${path}`, res.status);  // status is not a transport failure
    return await read(res);
  } catch (err) {
    if (err instanceof ServerError) throw err;                 // don't re-wrap a real answer
    throw new ServerError(`request failed: ${describeChain(err)}`);
  } finally {
    clearTimeout(timer);
  }
}

get  = (p, s) => s.parse(await this.exchange("GET",  p, undefined, r => r.json()));
del  = (p)    => void await this.exchange("DELETE", p, undefined, async () => null);
```

The abort **does** reach a body already in flight — undici errors the response stream on signal — so this
genuinely works once the timer survives long enough to fire.

## 2. `abort()` with no reason, and `cause` thrown away

`controller.abort()` rejects the fetch with `AbortError: This operation was aborted`, which names neither
the server nor how long it was given. Pass a reason and it propagates verbatim:

```ts
controller.abort(new Error(`no answer within ${ms}ms (${method} ${url})`))
```

Separately, undici reports every transport failure as a bare `TypeError: fetch failed` and hangs the one
informative sentence off `.cause`. `String(err)` discards it. Walk the chain, bounded so a
self-referential cause cannot spin:

```ts
function describeChain(err: unknown, depth = 4): string {
  const parts: string[] = [];
  for (let e: unknown = err, i = 0; e != null && i < depth; e = (e as { cause?: unknown }).cause, i++) parts.push(String(e));
  return parts.join(": ");
}
```

Measured difference, same three failures before and after:

```
before: AbortError: This operation was aborted     /  TypeError: fetch failed   (all three cases)
after:  Error: no answer within 1500ms (GET http://10.0.0.5:9999/System/Info)
        TypeError: fetch failed: Error: connect ECONNREFUSED 127.0.0.1:49999
        TypeError: fetch failed: Error: getaddrinfo ENOTFOUND no-such-host.invalid
```

Also worth carrying the HTTP **status** on the error object rather than recovering it later by regexing
the message (`/\b40[13]\b/` on a sentence matches any 401 in prose and misses the status the moment
someone rewords the message). The throw site already has it.

## Testing this: an injected fake cannot express the condition

Two harness traps, both of which produce a test that asserts nothing:

- **A hand-made `Response` is not wired to your `AbortController`.** `fetchImpl = async () => new Response(stream)`
  ignores the signal entirely, so a body that never ends hangs the *test* rather than being aborted. A fake
  can prove the message text; only a real socket can prove the deadline.
- **`res.writeHead()` alone does not flush headers.** In `node:http` the headers go out with the first
  `write()` or `end()`, so a "stall after headers" server written as `writeHead(200)` and nothing else
  actually stalls **before** headers. The client is then still waiting on the fetch — which the buggy code
  bounded perfectly well — and the test passes against the very bug it exists to catch.

The server that actually reproduces it:

```js
res.writeHead(200, { "Content-Type": "application/json" });
res.flushHeaders();      // required
res.write('{"Id":');     // partial body, never ended
```

Verify with a mutant: reintroduce `clearTimeout(timer)` right after the fetch and confirm the stall tests
now fail on the runner's own timeout. With the harness above they go from 6 passing in ~1 s to 3 failing
at 5 s; with the broken harness the mutant passes and tells you nothing.
