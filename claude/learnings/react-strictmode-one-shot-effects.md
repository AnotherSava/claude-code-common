# React StrictMode burns one-shot effect guards (set the flag from the outcome, not the attempt)

React 18/19 in development mounts every effect, runs its cleanup, and mounts it again. Any "do this exactly once"
guard whose flag is set on *attempting* the action is therefore spent by that throwaway first cycle — and the real
occurrence, later, is silently skipped. Production doesn't double-invoke, so this is a development-only symptom that
looks like a broken feature.

The shape that fails:

```ts
const sentRef = useRef(false);
const reportFinal = useCallback(() => {
  if (sentRef.current) return;
  sentRef.current = true;                 // ← spent even when the call below does nothing
  send(state.current);                    // early-returns: nothing is ready yet
}, []);
```

The first StrictMode teardown calls this before the async setup has produced anything, `send` bails, and the flag is
now `true` forever. The real teardown at the end returns immediately.

The fix is to let the action report whether it happened, and set the flag from that:

```ts
function send(...): boolean {
  if (nothingToSay) return false;
  void fetch(...);
  return true;
}

const reportFinal = useCallback(() => {
  if (sentRef.current) return;
  sentRef.current = send(...);            // only a real send consumes the one shot
}, []);
```

**Cleanup order matters too.** React runs effect cleanups in *declaration* order. If effect A's cleanup destroys the
thing effect B's cleanup needs to read, B must be declared first. Concretely: an hls.js `destroy()` detaches with
`media.removeAttribute("src"); media.load()`, and the HTML load algorithm sets the playback position to 0 — so a
"report where the user got to" cleanup has to be declared *above* the effect that owns the player, or it reports 0.

**Debugging note.** A doubled setup in the log — two negotiations, two sessions, two of whatever your effect starts —
is the tell that StrictMode is double-invoking, and a hint to audit every `useRef` guard the effect touches. Also
beware an effect that writes state it depends on: `if (x === null) setX(serverDefault)` inside an effect keyed on
`[x]` re-runs the whole effect, which for anything expensive (opening a stream, starting a transcode) means doing it
twice and orphaning the first. Read through to the fallback at the point of use instead — `x ?? serverDefault`.

Related: `nextjs-react-hooks-purity.md`.
