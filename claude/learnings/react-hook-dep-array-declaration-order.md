# A value in a useEffect dep array must be declared ABOVE the effect

Moving a `useCallback`/`useMemo` below the effect that lists it as a dependency is not a style choice — it throws
at render:

```
ReferenceError: Cannot access 'step' before initialization
```

Why it surprises: the effect **body** may reference anything in the component, declared above or below, because
the closure is only invoked after render commits. The **dependency array** is different — it is a plain array
literal evaluated as an argument to `useEffect` *during* render, in source order. A `const` declared later is
still in its temporal dead zone at that moment, so reading it is a hard error, not a stale value.

```tsx
// BROKEN — dep array is evaluated here, `step` is initialized 20 lines down
useEffect(() => {
  const onKey = (e: KeyboardEvent) => { if (e.key === "PageDown") step(next); };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [step, next]);

const step = useCallback((to: Item) => { /* … */ }, []);
```

Fix: hoist the `useCallback` above the effect. Do NOT "fix" it by dropping the value from the dep array (a stale
closure) or by wrapping it in a ref (hiding the ordering problem).

Failure modes to recognise:
- `function` declarations hoist, so a plain function used as a dep works while a `const` arrow does not — the
  same refactor can break only when a helper is converted to `useCallback`.
- Reordering hooks this way is safe for the Rules of Hooks: the *call order* of `useEffect`/`useCallback` must be
  stable across renders, but moving a declaration in the source changes that order identically on every render.
- It fails on first render, so a component behind a route/dialog can look fine until the feature is opened.
- The exception that hides it: with the value only inside the body and absent from the deps, `tsc` and
  `eslint-plugin-react-hooks` both stay quiet — the error appears the moment the dep is added correctly.
