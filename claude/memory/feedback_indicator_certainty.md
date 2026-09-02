---
name: feedback_indicator_certainty
description: A status indicator's positive state must be gated on confirmed evidence — unconfirmed gets its own pending state, never the healthy colour and never the off colour
metadata:
  type: feedback
---

For any status indicator, the positive "healthy" state (green, ✓, "connected", "passing") must reflect a *confirmed* good state — never a merely-plausible, not-yet-checked, or absence-of-negative one.

**Why:** The user pushed back on an indicator that went green whenever a check was "set up and not yet caught failing," which lumped in cases where the thing being checked had **never once been observed working**: "why does this one show green? it gives false sense of certainty." Green vouching for something unconfirmed is a false positive, and it is the expensive kind — the whole point of the indicator is that the user stops looking when it is green.

**How to apply:** Gate the healthy state on real positive evidence, not on the absence of a failure. Give "set up but unconfirmed" its own distinct state — *not* healthy (false certainty) and *not* the off/absent colour (which reads as "no indicator here at all", a false negative). The ladder is **off → pending/unknown → alive**, with a separate failed state, and the unknown rung is itself the useful signal: a pending that never advances is exactly how you discover a setup that silently never delivered. Applies to health checks, connection status, canaries, CI badges, sync state — anything with three or more states. Closely related to [[feedback_not_run_is_not_pass]] (a check that cannot distinguish success from never-ran) and [[feedback_no_guessed_facts]].
