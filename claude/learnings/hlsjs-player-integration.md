# hls.js — loader config, load events, and measuring delivery health

Verified against **hls.js 1.6.17** driving Jellyfin fMP4 output through MSE in Chrome 151. Line references are into
`node_modules/hls.js/dist/hls.mjs` and `hls.d.ts` of that version.

## `mergeConfig` is a SHALLOW spread — a partial policy silently deletes retries

This is the single most dangerous thing in the config surface.

```js
// hls.mjs
return _objectSpread2(_objectSpread2({}, defaultsCopy), userConfig);
```

Top-level keys are replaced wholesale, not deep-merged. So this:

```js
new Hls({ fragLoadPolicy: { default: { maxTimeToFirstByteMs: 60_000, maxLoadTimeMs: 120_000 } } })
```

replaces the entire default policy object and leaves `timeoutRetry` and `errorRetry` **undefined**. `getRetryConfig`
returns that undefined and `shouldRetry` returns false on its first line — so the *first* segment timeout or 5xx goes
straight to a fatal error instead of being retried 4 or 6 times.

`LoaderConfig` requires all four keys, and TypeScript will tell you *if* you annotate it — but `HlsConfig` is accepted
as `Partial<HlsConfig>`, so the nested object's missing keys are not caught:

```ts
export declare type LoaderConfig = {
    maxTimeToFirstByteMs: number;
    maxLoadTimeMs: number;
    timeoutRetry: RetryConfig | null;
    errorRetry: RetryConfig | null;
};
```

Always spell the whole policy. The stock defaults (hls.mjs `fragLoadPolicy`):

```js
fragLoadPolicy: {
  default: {
    maxTimeToFirstByteMs: 10000,
    maxLoadTimeMs: 120000,
    timeoutRetry: { maxNumRetry: 4, retryDelayMs: 0,    maxRetryDelayMs: 0 },
    errorRetry:   { maxNumRetry: 6, retryDelayMs: 1000, maxRetryDelayMs: 8000 },
  },
},
```

The **deprecated** single-value keys (`fragLoadingTimeOut`, `manifestLoadingTimeOut`, …) are *safer* in this one
respect: the deprecation shim mutates a deep copy of the defaults, so retries survive. It just spends one number on
both budgets — see below.

## `maxLoadTimeMs` is a TOTAL budget, not a transfer budget

```js
config.timeout = maxTimeToFirstByteMs && isFiniteNumber(maxTimeToFirstByteMs) ? maxTimeToFirstByteMs : maxLoadTimeMs;
// …once headers arrive:
config.timeout = config.loadPolicy.maxLoadTimeMs;
this.requestTimeout = self.setTimeout(this.loadtimeout.bind(this),
  config.loadPolicy.maxLoadTimeMs - (stats.loading.first - stats.loading.start));
```

`maxLoadTimeMs` is measured **from request start**, and the post-header timer is rearmed with
`maxLoadTimeMs − timeToFirstByte`. So `maxTimeToFirstByteMs: 60_000` with `maxLoadTimeMs: 30_000` is
self-contradictory: any TTFB above 30 s rearms with a negative delay and fires `FRAG_LOAD_TIMEOUT` the instant the
headers land. **The total must exceed the TTFB cap** — there is no way to give the wait a longer leash than the whole
request.

Splitting them is worth doing when the server legitimately blocks before responding (Jellyfin holds a segment request
open until ffmpeg has written the file). Give TTFB a long leash and leave the total at the stock 120 s.

## `FRAG_LOADED`, not `FRAG_BUFFERED`, if you want honest timings

`AbrController.onFragBuffered` overwrites `stats.bwEstimate` with its EWMA (hls.mjs ~:3791), after `XhrLoader` set the
real per-request wire rate (~:31149). If the server blocks before sending bytes, that EWMA charges the wait to the
network — so a stalled *transcode* reads as a broken *link*. Take the numbers at `FRAG_LOADED`.

At `FRAG_LOADED` the stats are already complete: `XhrLoader` writes `stats.loading.end` and
`stats.loaded = stats.total = len` **before** calling `onSuccess`, which is what resolves `_doFragLoad` and triggers
the event.

```js
hls.on(Hls.Events.FRAG_LOADED, (_e, data) => {
  if ((data.frag.type as string) !== "main") return;   // see below
  const { loading, loaded } = data.frag.stats;
  const ttfbMs     = loading.first - loading.start;    // server think-time
  const transferMs = loading.end   - loading.first;    // wire time
  const bytes      = loaded;                           // NOT `total` — see below
  const duration   = data.frag.duration;
});
```

- `FragLoadedData` has **no top-level `stats`** — it is `{ frag, part, payload, networkDetails }`. Reach `data.frag.stats`
  (`get stats(): LoadStats` is public on `BaseSegment`).
- Use **`loaded`, not `total`** — a response forwarded by your own proxy may carry no `Content-Length`.
- Init segments do **not** fire this (they go through `completeInitSegmentLoad`, which triggers nothing), and
  bandwidth-test fragments require `config.testBandwidth && levels.length > 1`, which a single-variant playlist never
  satisfies. So no `sn === 'initSegment'` filter is needed.

### Filter to the main rendition — and the obvious fix doesn't compile

Audio and subtitle renditions route through the same `BaseStreamController._loadFragForPlayback`, so they fire
`FRAG_LOADED` too, with wildly different byte counts for the same wall-clock second. Filter on `frag.type` — but
`PlaylistLevelType` is an ambient **`const enum`**, so under `"isolatedModules": true` importing it is `TS2748` and
comparing against a bare string is a no-overlap error. Cast:

```ts
if ((data.frag.type as string) !== "main") return;  // cast dodges the const enum; do not "fix" into an import
```

## Two arithmetic traps in the sample

- **`loading.end` is clamped** to be ≥ `loading.first` (`Math.max(self.performance.now(), stats.loading.first)`), so a
  same-tick response yields `transferMs === 0` and an infinite throughput. Drop the sample.
- **`hls.mainForwardBufferInfo` returns `null`** whenever the load position isn't a finite number. A `?? 0` turns
  "unknown" into "buffer is empty", which is the starving side of every threshold. Drop the sample instead of
  substituting.

Useful public getters: `get mainForwardBufferInfo(): BufferInfo | null` (`.len` is seconds ahead) and
`get ttfbEstimate(): number` (an EWMA that weights a 5 s sample at ~5e-6, so it stays clean as a round-trip baseline
even under sustained server-side blocking — a min-of-window baseline would rise *with* the fault and stop firing
exactly when it is most true).

## The buffer-full blind spot

**A sample-driven diagnostic goes silent in the one case that needs it most.** When the stream arrives faster than it
plays, the buffer fills to `maxBufferLength`, hls.js **stops requesting fragments**, and no further `FRAG_LOADED`
fires. If the picture then stops — a decoder handed something it cannot take — every fragment-based signal has already
gone quiet.

So decode health has to be read from the media element on a timer, not from the loader:

```js
const q = video.getVideoPlaybackQuality();   // droppedVideoFrames / totalVideoFrames
// plus: has currentTime advanced since the last tick, while !paused && !ended?
```

Check **both** dropped frames *and* a frozen playhead. A stream the machine cannot decode at all reports **zero**
dropped frames — it never decoded the frames it would have dropped — so the drop counter alone misses the worst case.
Diff the frame counters against a base retaken on every attach: they belong to the element and survive a source swap.

Also gate on "has it ever played", or a player that has yet to show its first frame is indistinguishable from one that
froze.

## `hls.destroy()` rewinds the element

`destroy()` calls `media.load()`, which resets `currentTime` to 0 and queues a `timeupdate` at 0 against a resource
that no longer exists. Two consequences when swapping streams:

- Any "remember where we were" read must happen **before** the teardown, and must be guarded on
  `readyState >= HAVE_METADATA` — before metadata `currentTime` is 0 whatever `startPosition` was set to, because
  hls.js applies `startPosition` only after the first fragment buffers.
- A `timeupdate` handler that records position should ignore events while `readyState === HAVE_NOTHING`, or a close
  during the swap reports position 0 over an almost-finished play.

## Misc

- `Events` is a plain `declare enum` (not `const`), so `Hls.Events.X` off a dynamically-imported `Hls` needs no static
  import — the code split survives.
- `bandwidthEstimate` exists and is maintained even with a single level, but it is the EWMA described above; prefer
  per-fragment arithmetic when you need to attribute a delay to a cause.
