# Next.js: host-locale-dependent sort in a client component → hydration mismatch

A `"use client"` component rendered by a Server Component is **still server-rendered** (SSR to HTML, then hydrated on the client). Any work its render does — including a `useMemo` body — runs **twice**: once on the server, once during the first client render. If that work depends on the **host environment** rather than only on props/state, the two runs can disagree and React throws a hydration mismatch (console error + a client re-render that can visibly reshuffle the DOM).

The classic offender is **`String.prototype.localeCompare(other)` with no locale argument**. Called with no locale it uses the *host's default locale and ICU/CLDR collation data* — Node (server) resolves its default from the process environment; the browser uses the user's UI language. When those disagree on ordering (e.g. server `en-US` vs a browser set to `sv`, where `å` collates after `z`), the SSR-emitted order differs from the client's.

```ts
// BAD — order depends on whoever's ICU runs it (server vs browser)
const byTitle = (a, b) => a.title.localeCompare(b.title);

// GOOD — pin the locale so both sides sort identically
const COLLATOR = new Intl.Collator("en");            // module-level: constructed once
const byTitle = (a, b) => COLLATOR.compare(a.title, b.title);
```

Key points:
- It is **not** limited to an explicit "sort by name" mode. Numeric/date sorts that fall through to a title tiebreak on **exact ties** (equal ratings, equal `createdAt` ms from a bulk import) hit the same unpinned compare, so the mismatch can fire even on a default view.
- The trigger is the compare running **during render on both sides**. The same `localeCompare` in a server-only data layer (an async Server Component, a `lib/` query) is fine — it runs once. Moving a sort from the server into a client component's `useMemo` is what introduces the exposure.
- `Intl.Collator("en")` reproduces `localeCompare`'s default ordering for ASCII/Latin titles (case-insensitive primary level: `alpha < Bravo < Charlie`), so pinning rarely changes visible behavior — it just makes it deterministic.
- Same class of bug for any **host-dependent API used during render**: `toLocaleString`/`Intl.DateTimeFormat`/`Intl.NumberFormat` without a fixed locale (and timezone), or `Date.now()`/`Math.random()` (those also trip Next 16's `react-hooks/purity` lint — see `nextjs-react-hooks-purity.md`).

Related: `javascript-nontransitive-comparator.md` (comparator correctness), `nextjs-react-hooks-purity.md` (impure render calls).
