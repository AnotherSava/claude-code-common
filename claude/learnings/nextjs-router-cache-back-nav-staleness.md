# Next.js App Router: stale UI on back-navigation, and how to keep just-mutated state

## Symptom

You mutate on a page (add-to-library, toggle, optimistic ✓), navigate away, then come **back** (browser back button, a `BackLink` calling `router.back()`, or re-opening the route) — and the page shows the **pre-mutation** state again. A hard reload fixes it; back-navigation doesn't. `revalidatePath()` in the Server Action didn't help.

## Root cause: the client-side Router Cache

The App Router has **four** cache layers, not one. The one that bites here is the **Router Cache** — it lives in the **browser**, in memory, and stores the RSC payload of visited/prefetched route segments for the session. History-POP navigations (back/forward, `router.back()`) are served **from this cache**, instantly, without refetching.

`revalidatePath()` / `revalidateTag()` purge only the **server** caches (Data Cache, Full Route Cache). They do **not** clear the client Router Cache in the same request. So back-navigation restores the RSC snapshot from before your mutation, and any optimistic-only React state (a `useState` ✓) resets to false on the remount.

**Diagnostic:** stale on back-nav but a hard refresh (Ctrl/Cmd+Shift+R) fixes it ⇒ it's the client Router Cache, not a server-cache misconfig.

## Fixes (pick by intent)

### 1. `router.refresh()` after the mutation (idiomatic, refetches)
Clears the Router Cache for the current route and refetches its RSC, so the updated entry is what back-nav later restores.
```tsx
await saveAction(...);
router.refresh(); // purges the client Router Cache for this route
```
Downside: a refetch (server round-trip / re-run of any data fetch) on every mutation.

### 2. Module-memory overlay (robust; keeps the cached page, overlays one bit)
Often the cached page-as-you-left-it is exactly the "same state on return" you WANT (same query, scroll, results, instant). You only need the **one mutated bit** to survive. Keep it in **module memory** — a module-level `Set`/`Map` in a `"use client"` module. It survives client navigation (push/back/forward) because the JS module stays loaded; it clears on a full reload, at which point the dynamic server render (straight from the DB) is authoritative again.
```tsx
"use client";
// Survives client nav; clears on full reload. Keyed however identifies the row.
const addedThisSession = new Set<string>();

export function Card({ item }: { item: Item }) {
  const key = `${item.type}:${item.id}`;
  // Lazy initializer reads module memory on (re)mount — so a back-nav remount keeps the ✓.
  const [added, setAdded] = useState(() => addedThisSession.has(key));
  const inLibrary = item.inLibrary || added; // server truth OR this-session add

  const onAdd = () => startTransition(async () => {
    await addAction(item);
    addedThisSession.add(key);
    setAdded(true);
  });
}
```
No refetch, no flash, works regardless of the exact cache behavior. This is the belt-and-suspenders choice when you've been fighting the cache and want it to *just work*.

Server-side complement: make the list query mark status **in place** (annotate each row with its library/selected status where it sits) rather than moving mutated rows to a separate section. Then even a full reload renders the row unchanged-but-flagged, coherent with the module-memory overlay — and nothing reorders under the user mid-mutation.

## Related trap: bare-route state loss (URL-carried state)

Distinct but adjacent: a **nav link to a bare route** (e.g. a header "Search" link → `/search` with no `?q=`) drops state that only lived in the URL, so returning "sometime later" via the nav shows an empty page. (Browser-back is fine here — the URL in history still carries `?q=`.) Fix: persist the last state in **`sessionStorage`** (per-tab, transient — the right scope for search/filter state; survives client nav and reloads within the tab), and restore it on mount when the route is bare:
```tsx
// Save whenever the page has state.
useEffect(() => { if (query) sessionStorage.setItem(KEY, JSON.stringify({ q: query, scope })); }, [query, scope]);

// Restore once, only when we arrived bare. A deliberate "clear" removes the key so this won't re-fill.
const checked = useRef(false);
useEffect(() => {
  if (checked.current) return;
  checked.current = true;
  if (query) return; // arrived with state — nothing to restore
  const raw = sessionStorage.getItem(KEY);
  const saved = raw ? JSON.parse(raw) : null;
  if (saved?.q) router.replace(`/search?${new URLSearchParams({ scope: saved.scope, q: saved.q })}`);
}, [query, router]);
```
Trade-off: a brief empty-flash before the restore `router.replace` lands. If that matters, restore server-side instead (write a cookie on change; the Server Component reads it and `redirect()`s a bare route to the state-bearing URL — no flash).

## See also
- `nextjs-router-refresh-optimistic-hold.md` — a *different* facet: the ~1 s **stale-prop flash** while `router.refresh()`'s refetch is in flight (hold just-saved values across the gap, clear on a prop-reference/version change). That's about the refresh *gap within a page*; this doc is about *back-navigation* restoring a whole stale cached page.
