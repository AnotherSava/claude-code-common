# Next 16: react-hooks/purity errors on Date.now() / Math.random() in components

Next 16's ESLint setup (eslint-plugin-react-hooks v6 / the react-compiler-adjacent rules) ships a `react-hooks/purity` rule that **errors** on impure calls during render — `Date.now()`, `Math.random()`, argless `new Date()` — **even inside async Server Components**:

```
error  Cannot call impure function during render — `Date.now` is an impure function  react-hooks/purity
```

A **dynamic** Server Component (cookie/DB-dependent, rendered once per request, never memoized) can legitimately read the wall clock — e.g. to compute "time ago" freshness. That's not a real purity hazard the way a memoized client component would be, so the fix is a scoped disable **with a reason**, not a refactor:

```tsx
// Dynamic server component: needs the request-time clock for "time ago"; renders once per
// request and is never memoized, so reading it here is safe.
// eslint-disable-next-line react-hooks/purity
const nowMs = Date.now();
```

**The other fix — a one-line module wrapper, no directive at all.** The rule flags the impure call *in a render body*; a call into a module is not flagged, so exporting `nowMs()` from a `lib/` module lets every page read the clock with no per-call-site disable:

```ts
// lib/time.ts
export function nowMs(): number {
  return Date.now();
}
```

Prefer this once more than one page needs the request-time clock — the disable comment has to be re-argued and re-approved at each call site, and one of them will eventually be a memoized client component where the rule was right. Both the What's Next and scheduler apps do it this way. It only papers over the rule rather than satisfying it, so keep the justification in the wrapper's own doc comment where it is written once.

**Gotcha — directive placement:** `eslint-disable-next-line` disables the *immediately following* line. If you put a two-line explanatory comment *between* the directive and the code, the directive targets the comment (→ "Unused eslint-disable directive" warning) and the original error still fires. Put the prose explanation **above**, and the `// eslint-disable-next-line …` as the **last** line before the statement.

Note: `new Date(iso)` / `new Date(ms)` with an argument is pure (deterministic) and is **not** flagged — only the argless/impure forms are.
