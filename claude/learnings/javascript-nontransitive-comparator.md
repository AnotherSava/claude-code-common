# Non-transitive Array.sort comparators (a conditional key + a global fallback)

`Array.prototype.sort(cmp)` requires a **consistent, transitive** comparator. If the comparator applies one ordering key to only a SUBSET of pairs and a different key to the rest, it can become non-transitive — and V8 does not throw, it silently returns a **scrambled** order (not merely a mis-sorted one). The scramble is the tell: the output matches **neither** the previous ordering nor the intended new one, so it looks random.

## Concrete case (what's-next / shows list)

A flat list of shows is sorted, then regrouped into shelves (Behind / Planned / Up-to-date / …). Goal: order the *Behind* shelf by last-watched-desc, leave the other shelves by most-behind. First attempt:

```js
// BROKEN — non-transitive
function rank(a, b) {
  return Number(b.fav) - Number(a.fav)
    || behindRecency(a, b)                     // lastWatched desc — but returns 0 unless BOTH are group "behind"
    || (b.unwatchedCount - a.unwatchedCount)   // "most behind" — applies to ALL pairs, incl. behind-vs-other
    || a.title.localeCompare(b.title);
}
```

`behindRecency` returns 0 for any pair that is not behind-vs-behind, but the `unwatchedCount` fallback orders behind-vs-*planned/stopped* pairs too (planned/stopped shows also have unwatched episodes). That produces cycles like `stopped < behindA < behindB < stopped`, V8 bails, and the Behind shelf renders in garbage order.

## Fix: make the conditioning dimension the PRIMARY key

Sort by group FIRST, so the conditional key (`behindRecency`) is only ever evaluated for same-group pairs — cross-group pairs are decided by the group rank and never fall through to the conditional/fallback keys. Now transitive.

```js
const GROUP_RANK = new Map(GROUP_ORDER.map((g, i) => [g, i]));
function rank(a, b) {
  return (GROUP_RANK.get(a.group) ?? 0) - (GROUP_RANK.get(b.group) ?? 0)  // PRIMARY: groups never interleave
    || Number(b.fav) - Number(a.fav)
    || behindRecency(a, b)                      // now only sees same-(behind)-group pairs → consistent
    || (b.unwatchedCount - a.unwatchedCount)
    || a.title.localeCompare(b.title);
}
```

## Rule of thumb

A comparator key gated on a predicate P (returns 0 unless BOTH items satisfy P) is safe only if some earlier key already fully separates P-satisfiers from non-satisfiers. Otherwise a later unconditional key can form a cycle. Easiest guarantee: sort by the grouping/predicate dimension first.

## Debugging signature

If a `.sort()` result matches NEITHER the old behavior NOR the intended new one (looks random), suspect non-transitivity **before** suspecting a data / deploy / cache problem. A one-shot log of the post-sort order printing each item's competing keys confirms it in one request — that's how the case above was pinned after "stale render" and "did the build pick it up?" were ruled out.
