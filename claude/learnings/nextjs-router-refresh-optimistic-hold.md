# Next.js App Router: holding just-saved state across the `router.refresh()` gap

## The stale-prop flash

In the App Router, a Client Component that saves via a Server Action and then calls `router.refresh()` will **flash the pre-save values** for roughly the second the refetch takes. The mechanism:

- `router.refresh()` re-runs the Server Components and streams new props down, but that is **asynchronous** (a network round-trip on the server).
- The Client Component's `useState` **survives** the refresh (it does not unmount) — but its **props lag** until the refetch lands.
- So the instant you clear your local edit state on the action's success, the component re-renders with the **stale** props (the old server data). It shows the old values, then snaps to the new ones ~1 s later when the fresh props arrive.

The symptom the user sees: "I saved, and machine time / the total / the row reset to the previous value for a second, then went back to the new value."

## The fix: optimistically hold the just-saved values, clear on fresh props

Hold the just-saved values in local state and **display them in preference to the (stale) props** during the gap. Clear the hold the moment fresh props actually arrive.

The critical part is **detecting "fresh props arrived."** Two reliable signals:

1. **A prop reference change.** A server re-render mints brand-new objects, so an object prop (e.g. the fetched `quote`) gets a new reference on refresh. A re-render caused by your *own* state change keeps the *same* prop reference — so the held snapshot survives until the real refetch.
2. **A version field.** Any scalar the mutation bumps: an `updatedAt`-derived number (`row.updatedAt.getTime()`), a row version, etc. Prisma bumps `updatedAt` on every `update`, so it changes exactly on the mutation's refresh.

Use the React **"adjust state during render on a prop change"** pattern to clear — NOT a `useEffect` + `setState` (which is the wrong tool and trips the `react-hooks/set-state-in-effect` lint rule; it also adds an extra render and is subtly wrong under concurrent rendering):

```tsx
// Hold the just-saved values across the refresh gap.
const [held, setHeld] = useState<Saved | null>(null);

// Clear the hold when fresh props arrive — reset-state-on-prop-change (render phase, no effect).
const [seen, setSeen] = useState(row.version);      // or: useState(quote) to compare by reference
if (row.version !== seen) {
  setSeen(row.version);
  setHeld(null);
}

// Display prefers the held snapshot over the (possibly stale) props.
const shown = held ?? fromProps(row);

async function save() {
  const r = await saveAction(...);
  if (!r.ok) { setError(r.error); return; }
  setHeld(justSavedValues);   // freeze what we just wrote
  router.refresh();           // fire-and-forget; held covers the gap
}
```

React runs a render-phase `setState` synchronously and re-renders before committing — this is the documented, concurrency-safe way to derive/reset state from props. `setHeld(null)` when `held` is already `null` is a no-op (React bails), so the only cost on an unrelated refresh is the `setSeen` bump.

## Hold the whole subtree the refresh will restate

`router.refresh()` restates *everything* the Server Component produces, so any sub-view fed by those props can flash — not just the field you edited. Hold each independently:

- The primary edited value(s).
- Any **derived / sibling views** that read the same server data (a totals breakdown, a summary panel, per-row computed figures, a preview list). If the refresh will change them, hold a snapshot for each.
- Freeze a **computed** view (e.g. an already-mapped list) via a ref that mirrors the last render (`ref.current = computed` during render), then read the ref at save time — you can't recompute it after you've cleared the inputs.

## Notes

- `router.refresh()` returns `void` — you cannot `await` it. That's *why* you need the hold + prop-change detector rather than "await, then clear."
- Don't dim / show a "loading…"/"calculating…" affordance during this gap unless work is genuinely happening. The compute already ran inside the Server Action; the gap is just a refetch, so a spinner misrepresents it — hold the real values crisply instead.
- If the action's cross-cutting effects mean the held snapshot ≈ (but not exactly) the refreshed value (e.g. a discount recomputed on a new base), that's fine: the transition held → authoritative is a small, correct settle, far better than a flash to the *old* value.
