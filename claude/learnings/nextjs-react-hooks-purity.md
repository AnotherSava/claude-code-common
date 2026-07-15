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

**Gotcha — directive placement:** `eslint-disable-next-line` disables the *immediately following* line. If you put a two-line explanatory comment *between* the directive and the code, the directive targets the comment (→ "Unused eslint-disable directive" warning) and the original error still fires. Put the prose explanation **above**, and the `// eslint-disable-next-line …` as the **last** line before the statement.

Note: `new Date(iso)` / `new Date(ms)` with an argument is pure (deterministic) and is **not** flagged — only the argless/impure forms are.
