---
name: feedback_check_the_network_exists
description: before recommending a feature whose value depends on other users, check whether those users exist yet
metadata:
  type: feedback
---

A feature that only works once other people are using the product is worth nothing at launch. Check the cold-start case before calling such a design better.

**Why:** asked to show which of a user's friends were attending an activity, I compared two approaches and called the in-app one — matching against other users of our own app — "arguably the better feature", because it needed no third-party permissions and showed intent rather than just commitment. The user replied that it requires other people to use the product, which they did not expect yet. They were right, and it mattered: the third-party source already contained every participant, so it worked from day one, while my preferred design would have shown an empty list indefinitely. I had nearly argued us out of the only approach that functioned.

**How to apply:** for anything social, collaborative, or comparative, ask what it does with exactly one user. If the answer is "nothing", it is a later feature regardless of how much cleaner it is — say so explicitly rather than ranking it first. Where an existing external system already holds the network, that is usually the cold-start-proof route even when it is uglier. Both can coexist: ship the one that works now, and let the in-app version take over as the user base makes it viable.
