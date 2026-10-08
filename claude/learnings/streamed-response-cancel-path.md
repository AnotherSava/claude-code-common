# The cancel path of a streamed response, and why a test of it lies

A handler that streams a large body wants two properties: the consumer sees bytes before the source is
exhausted, and abandoning the download releases whatever the source holds — a database cursor, a file
handle, a lock. Both are easy to get wrong in ways that read correctly, and a test of either can pass
or hang for reasons that have nothing to do with the code under test.

## A manual `.next()` loop does not finalize the inner generator

`for await (const x of gen)` performs IteratorClose on any abrupt exit, so returning the *outer*
generator propagates down and the inner one's `finally` runs. A hand-written loop over `.next()` does
not — there is no implicit close, so the inner generator stays suspended forever with everything it
holds still open.

```js
// Propagates a return(): the for-await closes `lines`.
for await (const line of lines) { ... }

// Does NOT: nothing finalizes `lines` when this generator is returned.
for (let next = await lines.next(); !next.done; next = await lines.next()) { ... }
```

The manual form is not gratuitous — it is what you write when the first yield is special, a header line
read before the body. The fix is to say the finalization out loud:

```js
try {
  const first = await lines.next();     // the header
  ...
  for (let next = await lines.next(); !next.done; next = await lines.next()) { ... }
} finally {
  await lines.return(undefined);
}
```

Measured on a backup exporter: a `ReadableStream`'s `cancel` handler called `return()` on the generator
it pulled from, which had previously been the generator that owned the database cursor. Interposing a
second generator that drove the first by hand silently moved the cursor out of reach — the cancel still
ran, the stream still closed, and the server-side cursor stayed open. Nothing failed; a test asserting
the cursor closed just stopped passing.

Prefer `for await` wherever the shape allows it, and where it does not, write the `finally` rather than
relying on delegation. `yield*` into a nested generator does forward a return completion, so the trap is
specifically the hand-written `.next()` loop, not nesting as such.

## A compressible source drains far ahead of the consumer, and its output barely trickles

Node's `CompressionStream` reports a writable `desiredSize` that never falls, so a pipe reads ahead as
fast as the source will answer, while zlib emits only when its own output buffer fills. On compressible
input that happens rarely, so the consumer gets a few small chunks while the source runs to the end.

Measured on v24.19.0, twenty 512 KiB documents through a gzip stream:

| Source content | First chunk | Source read by then | Whole stream |
|---|---|---|---|
| A repeated character | 10 bytes — the gzip header | the first read | 10, 4110, 4108, 1994 |
| Deterministic noise | 16,384 bytes | 17 of 20 | 661 chunks |

The header arrives on the very first read, so nothing is withheld until flush; what is withheld is any
useful *volume*. The 4,110-byte chunk came at 10 of 20 documents read and the 4,108-byte one at 18 of 20,
leaving only the last 1,994 bytes for the flush.

So a test that reads one chunk and then cancels, expecting to catch the source mid-flight, catches
nothing it can act on: the first chunk is ten bytes of header, and by the second the source is half
drained. A consumer waiting for a byte threshold fares worse still — 10 MiB of a repeated character
compresses to 10,222 bytes in four chunks, so a 64 KiB threshold is never crossed at all and the stream
simply ends, where noise crosses it four chunks into 661.

Two consequences:

- **Fixtures for a cancel test must resist compression.** Use a deterministic PRNG rather than
  `Math.random`, so the case is reproducible:

  ```js
  function noise(length) {
    let seed = 12345;
    let out = '';
    for (let at = 0; at < length; at += 1) { seed = (seed * 1103515245 + 12345) & 0x7fffffff; out += String.fromCharCode(33 + (seed % 90)); }
    return out;
  }
  ```

- **A fixture must also outgrow whatever the producer buffers.** Where the producer batches before
  emitting — a tar member, a write-combining buffer — a source smaller than one batch is finished before
  a single byte reaches the stream, whatever its compressibility. Both conditions have to hold at once,
  and failing either looks identical: the test times out waiting for an event that will never happen.

## Cancellation propagation is asynchronous — assert on the event

`reader.cancel()` resolving does not mean the source's `cancel` has run. Through a `pipeThrough`, the
abort reaches the upstream source some ticks later, and a `ReadableStream` will not call `cancel` while
a `pull` is still in flight — so with a batching producer the cancel can only land *between* batches.

Read the state through a promise the fake resolves, never after a fixed number of ticks:

```js
const { db, closedEarly, cursorClosed } = fake(...);
const reader = stream.getReader();
await reader.read();
await reader.cancel();
await cursorClosed;              // resolved by the fake's own `return()`
expect(closedEarly).toEqual(['bookings']);
```

## Measure it outside the test before changing the test

When a cancel test starts timing out after a refactor, the question is whether the production path broke
or the fixture stopped reaching the state. Both look like a hang. A throwaway script that prints *how
much of the source was consumed when the first chunk arrived*, and *whether the cancel reached the
generator*, answers it in one run — and distinguishes the two findings above, which have the same
symptom and opposite fixes.
