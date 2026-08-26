# A filter whose "all" state is an absent URL param cannot be given a default later

The natural way to put a single-choice filter in the URL is: `?day=2026-08-22` narrows, and no `day` at all
means every day. It reads well, keeps the bare URL clean, and the "All" control just submits an empty value.

It also quietly forecloses one future change: **giving that param a computed default**. The moment a bare URL
means "work it out for me", the absent param has two jobs — "I chose everything" and "I chose nothing yet" —
and the UI can no longer express the first. Clicking All submits nothing, the server sees no param, applies the
default, and the user lands right back where they were. The control looks broken and the bug is in the
encoding, not the handler.

Concretely: a convention schedule that should open on today's day during the event. Before, `?day=` absent
meant all days; after, it has to mean "today, if the event is on". Those are different answers to the same URL.

## The fix: give "all" a value

```ts
export const DAY_PARAM = 'day';
export const DAY_ALL = 'all';           // explicit, so it is distinguishable from "unset"
```

```ts
// reading: the sentinel reads out as no filter
day: ((v) => (v === DAY_ALL ? undefined : v))(first(query[DAY_PARAM]))

// defaulting: only fill in a URL that names nothing, and only with a value that exists
const named = first(query[DAY_PARAM]);
const filters = browseFiltersFrom(
  named === undefined && days.includes(today) ? { ...query, [DAY_PARAM]: today } : query,
);
```

Three states, all reachable and all shareable:

| URL | Means |
|---|---|
| `?day=2026-08-22` | that day, forever |
| `?day=all` | every day, forever |
| bare | whatever day it is when you open it |

## What to weigh before doing it

- **It changes what old links mean.** Anything already shared with no `day` used to mean "all" and now means
  "today". Fine for a single-user app; a public one wants a redirect or a new param name.
- **Default only to a value that exists.** Defaulting to "today" when today has no rows filters the page to
  nothing, which is worse than the original behaviour. Check membership against the real list first — which
  usually means fetching that list *before* the filters, not alongside them.
- **The bare URL is now time-dependent by design.** Say so in a comment, or the next reader will "fix" it.

## The general rule

Absence is a fine encoding for a boolean-ish default that will never be computed — an unticked checkbox that
means off. It is a bad encoding for any choice you might later want the server to make on the user's behalf,
because you cannot distinguish "unset" from "explicitly the wide option" without adding the value you should
have had from the start. When a filter has a natural "everything" state, give it a name.
