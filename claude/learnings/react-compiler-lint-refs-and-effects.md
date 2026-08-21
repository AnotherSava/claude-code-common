# Next 16 react-hooks rules: no refs during render, no setState in an effect body

`eslint-config-next@16` ships the React Compiler-adjacent rules as **errors**, not warnings. Two of them fire on patterns React's own docs still show, and between them they rule out the obvious ways to sync state from props and to debounce. Sibling note: `nextjs-react-hooks-purity.md` covers `react-hooks/purity` (`Date.now()` during render).

## `react-hooks/refs` — a ref may not be touched during render

```
error  Cannot access refs during render … Accessing a ref value (the `current` property) during
       render can cause your component not to update as expected  react-hooks/refs
```

It flags **both** reads and writes, including the "store the previous prop" trick:

```tsx
const sent = useRef(incoming);
if (incoming !== sent.current) {   // ← error: cannot access refs during render
  sent.current = incoming;         // ← error: cannot update ref during render
  setValues(applied);
}
```

**Fix:** keep the previous value in *state*, which is what React's "adjusting state when a prop changes" pattern actually prescribes:

```tsx
const [sent, setSent] = useState(incoming);
if (incoming !== sent) {           // fine: plain state comparison during render
  setSent(incoming);
  setValues(applied);
}
```

Setting state during render is legal (React re-renders before committing children) and is *not* flagged — only refs are.

## `react-hooks/set-state-in-effect` — no synchronous setState in an effect body

```
error  Calling setState synchronously within an effect can trigger cascading renders
       react-hooks/set-state-in-effect
```

So the fallback of "do the prop sync in an effect instead" is closed too:

```tsx
useEffect(() => {
  if (incoming === sent) return;
  setSent(incoming);               // ← error
  setValues(applied);
}, [incoming, sent]);
```

setState **inside a callback** the effect registers — a timer, a listener, a promise `.then` — is fine. Only the synchronous body is flagged.

## What the two rules push you towards

Between them: **prop→state sync goes in render**, and **anything needing a ref goes in an effect**.

A debounce is the case where this bites, because the naive version wants a ref for the timer id *and* wants to cancel when props change. Expressed as an effect that arms the timer and cancels in cleanup, it needs neither a ref nor a body setState — and gets correct cancellation for free, since React runs the cleanup whenever the deps change or the component unmounts:

```tsx
// `sent` is what we last asked the server for; `values` is what the controls show.
useEffect(() => {
  if (signatureOf(values) === sent) return;   // nothing outstanding
  const timer = setTimeout(() => navigate(values), 300);
  return () => clearTimeout(timer);           // typing again, or an outside change, cancels
}, [values, sent, navigate]);
```

For the deps to be stable, hoist the pure parts (URL building, serialisation) to module scope and wrap the one closure the effect calls in `useCallback` — otherwise a new function identity re-arms the timer on every render.
