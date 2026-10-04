---
name: feedback_minimal_v1_first
description: Lead a new feature's design with the smallest end-to-end v1; enrichments go in a "Later" section, not into the first design
metadata:
  type: feedback
---

When designing a new feature, lead with the smallest version that works end to end, and put enrichments in a
"Later" section of the same document rather than into the first design.

**Why:** on 2026-10-04 a design for a rutracker browser extension (What's Next) came back with chips on every
search result, release preferences, a search-context bar and a send row on topic pages. The user cut it with
"too complicated for the first version": they search themselves, so v1 became one toolbar button that hands
the page to the app. Cutting it also removed an auth token, a settings section and most error states — scope
that the feature-rich draft had made look necessary.

**How to apply:** before presenting a feature design, name the one action that delivers the outcome and
design that first; check what the user already does by hand that the design is replacing, since keeping their
manual part is often what makes v1 small. Keep the richer ideas, written down under "Later", so nothing
researched is lost. Related: [[feedback_no_premature_abstraction]].
