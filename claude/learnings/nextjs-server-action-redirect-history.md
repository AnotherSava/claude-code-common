# Next.js: a server action's `redirect()` and the history stack

Two behaviours of the App Router (measured against Next 16.3.1's source) that decide what a redirect from a
server action actually does to the browser's history and to navigations made while the action runs.

## `redirect()` inside a server action pushes by default

`redirect(url)` takes an optional second argument, `RedirectType` (`'push' | 'replace'`). Its default depends on
where it is called: `type ??= isAction ? 'push' : 'replace'` in `next/dist/client/components/redirect`. In a
server component or route it replaces; **inside a server action it pushes**, so the address the user was on stays
one Back away.

That matters whenever the redirect exists to move the user *off* a state that has just become wrong. The case
that exposed it: a review page kept per-item UI state in its query string, positional references into a record
an action was about to replace. The action redirected to the address without those entries, and Back then
returned to the old address and re-applied them to the new record — the exact outcome the redirect was written
to prevent. The fix is one argument:

```ts
import { RedirectType, redirect } from 'next/navigation';

redirect(after, RedirectType.replace);
```

Ask of any action-side redirect whether the page it leaves should still be reachable by Back. If not, replace.

## A navigation while an action is pending discards the action's result

In `next/dist/client/components/app-router-instance.js`, dispatching `ACTION_NAVIGATE` or `ACTION_RESTORE` while
a server action is pending sets `actionQueue.pending.discarded = true` and starts the navigation at once
(its comment: navigations "take priority over any pending actions"). When the discarded action settles, its
reducer state — including any redirect — is never applied; if it revalidated, only a refresh follows, and that
targets the URL the user navigated to.

So a `<Link>` click made while a slow action runs is not undone by the action's redirect when it lands. A
redirect computed from the page as it was rendered (a hidden form field carrying "where to go after") is safe
against later clicks for this reason, and needs no guard of its own. This holds for client navigations through
the router; it says nothing about a full page load.
