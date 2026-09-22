---
name: feedback_landing_route_chooses_not_renders
description: A landing route should choose a destination and redirect, never render one — a nav that must be told what the page rendered is the smell
metadata:
  type: feedback
---

A landing route — `/`, a dashboard root, any "what should I be looking at" entry point — should **choose a
section and redirect**. A route that both picks and *is* one of the things it picks between creates three
problems at once, and the middle one is the diagnostic.

**Why:** the trips app's `/` rendered the in-progress trip when there was one, else a list of what was
coming, else what had finished. The consequences, in order of how easy they are to notice:

1. **The content had no address.** The trip you were on was reachable only by loading `/` on the right day.
   Nothing could link to it, bookmark it, or be sent to someone.
2. **The nav had to be handed a `homeShows` field naming what `/` had rendered**, because there was no path
   for it to match against — otherwise the page most visits start at highlighted nothing. *That field is
   the smell.* A navigation component that must be told what the current page chose is proof the page has
   no address of its own.
3. **Back and forward were ambiguous**, because `/` meant different content at different times.

Replacing it with a one-line `redirect(sectionFor(...))`, and giving every section its own URL, removed all
three — and `homeShows` deleted itself, along with the view union and the mode-picking function behind it.

**How to apply:**

- Keep the choosing **pure and separate**: `sectionFor(state) → '/path'`, so the priority order is pinned by
  tests without a database, and the route is one line.
- Make the fallback a real page rather than a sentence. The last resort in the chain should be a section
  that renders its own empty state, not a homepage explaining that it has nothing to show.
- **Look for the smell in reverse.** Any prop telling a shared component what a *sibling* rendered is
  usually a missing URL. That is the cheapest place to catch this, because it shows up as an awkward field
  long before anyone misses the bookmark.
- One exception worth naming: where the chosen section carries mutating controls, the redirect is not
  merely tidier but required. A server action POSTs to the URL of the page that rendered it, so rendering
  such a section at a deliberately public `/` would make that route a write endpoint.
