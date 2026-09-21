---
name: Make the state settable, don't build a viewer for it
description: To see a view that only renders under some state, expose the input that state comes from — never build a preview block, scaffold route or fixture screen that imitates it
metadata:
  type: feedback
---

When a view only appears under a condition you cannot reach — a trip in progress today, a user with a role you do not have, a date that has not arrived — make the condition settable and let the real view render. Do not build a preview block, a scaffold route, or a fixture screen that reproduces what it would look like.

**Why:** 2026-09-20, on the trips app. The homepage's in-progress view needed a trip running *now* and none was. I offered a temporary preview block drawn from the previous trip; rejected. I then built a `/previous` route and a nav entry for it; rejected too. What was asked for was "an option to set current time/date — one that is used to determine past and upcoming trip, and also if any of the trip is happening now". One development-only override of `now`, read by every screen, replaced both scaffolds and was strictly better: it exercises the real code path rather than a copy of it, it reaches every dependent screen at once — the lists and the nav counts moved with it — and there is no second surface to keep in step or to delete later. A viewer can only ever show one state, and it shows it through code that is not the code that runs.

**How to apply:** Ask what input the view is a function of, and make *that* settable — behind a development-only gate where a fake value would be a lie in production. The scaffold is the tell: if you are about to build something whose only purpose is to let you look at something else, the thing you are looking at has an input you have not exposed. Related: [[feedback-no-permanent-logic-for-one-time]], because the scaffold is also durable surface for a one-off, and [[feedback_verify_at_the_user_visible_layer]], because the real path is the one worth looking at.
