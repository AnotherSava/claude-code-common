---
name: feedback_diagnosis_ends_with_a_plan
description: When a "why is it like this?" question turns out to be answered by "the feature was never built", the reply ends with how to proceed — findings describe the hole, a plan is what the user can decide on
metadata:
  type: feedback
---

When a diagnostic question turns out to be answered by "that was never built", the reply ends with a
plan. Findings describe the hole; they are not a thing the user can act on.

**Why:** measured 2026-10-01. The question was why one session showed DONE rather than CLEAN after
servicing a request to pull. The answer took an audit: the sending half of the feature existed, the
receiving half had never been written, the code's own doc comments claimed otherwise, and nobody had
parked it. All of that was reported — accurately, with evidence — and the reply closed on "both repos
are level with `origin/main`; this one is clean." Oleg's entire next message was *"i don't see a plan
on how do we proceed with this feature in your answer."*

The failure is not thoroughness. Everything in that report was true and most of it was needed. What
was missing is that a diagnosis which ends in missing work has changed what the turn is *about*: the
user asked a question and now holds a decision instead, and nothing in a list of findings tells them
what their options are or what it costs.

**How to apply:** when the root cause is "unbuilt" rather than "misbehaving", write the steps. Say
what attaches where, name the precedent in the codebase each step mirrors, and keep the asking down to
the decisions genuinely theirs — one or two, each phrased so either answer is actionable. Everything
that follows from the audit is yours to decide and should arrive decided, with the reasoning available
but not blocking. This is the same instinct as [[feedback_do_it_dont_offer_a_memo]] one level up: that
one says settle the concrete item rather than filing it, this one says settle the *shape of the work*
rather than handing over a diagnosis. [[feedback_lead_with_the_rule]] governs how the plan's own
sentences open.
