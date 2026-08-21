---
name: feedback_no_negative_from_partial_probe
description: having tested some paths and found nothing, report what you tested — not that the thing is impossible
metadata:
  type: feedback
---

When investigation comes back empty, state what was tested and what it returned. Do not convert a partial negative result into a general impossibility.

**Why:** after probing three endpoints on a third-party API and getting `441 session required` from each, I wrote "there is no way to learn who is in a game. That path is closed; we should stop spending on it." The user disproved it with a single screenshot of the ordinary public web page, which listed the people by name. The data was reachable the whole time via an `_include` on a request the code was already making 800 times per sync. The cost of the overclaim was not just being wrong — it was a recommendation to abandon a feature that turned out to be free.

**How to apply:** say "the endpoints I tried don't expose it — here they are", and name them. Before concluding something is unreachable, check the product's own UI: whatever it displays is by definition obtainable, and the network panel names the call. Be especially wary where absence carries no information — an API that silently ignores unknown parameters returns no key for a typo either, so "the field wasn't there" never proves a permission gate. Related: [[feedback_no_guessed_facts]], which covers asserting an identifier you never verified; this is the mirror image — asserting a limit you never established.
