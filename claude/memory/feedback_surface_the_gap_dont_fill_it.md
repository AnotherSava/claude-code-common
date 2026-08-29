---
name: feedback_surface_the_gap_dont_fill_it
description: Don't auto-fill a field a human must vouch for — leave it empty, mark it, and let them fill it by hand
metadata:
  type: feedback
---

**Don't fill an empty field with a machine's guess when a human is the one who has to vouch for it. Show that
it is empty.** Leave the value null, render a marker where it would have appeared, and let the degraded
behaviour stay honest — an operation that visibly asks "which one did you mean" beats one that confidently
goes somewhere wrong.

**Why:** once stored, a guessed value is indistinguishable from a checked one. It reads as authoritative in
every screen, export and calculation downstream, and it fails silently at exactly the moment someone is relying
on it. An absent value can be detected, counted and reported; a plausible wrong one cannot. The asymmetry is
the whole argument: the cost of the gap is a little friction now, and the cost of the guess is a failure later,
at the worst time, with nothing to warn you.

Observed 2026-08-28 (trips): half the stored places had no coordinates, so their map links were text searches
that could land on a disambiguation screen. I geocoded them to make the links exact. The user's answer — *"let's
not try to fill in empty, but add some warning icon before the name, so that user could see it when planning
the trip, check the location and add coordinates manually"* — is the better design, because the map link is
used under time pressure and a wrong pin is worse than a visible question mark.

**How to apply:**

- Prefer null plus a marker over a filled-in guess, whenever a person is the authority for that field.
- Make the marker visible where the work happens, not on a separate report — the point is to catch it while
  planning, not to audit it afterwards.
- Where the guess is genuinely useful, keep it out of the same field: record provenance beside it, or keep it
  as a *suggestion* in the edit UI that a human accepts. Never write it into the field the app treats as fact.
- If a field can only be filled by hand, say so in the plan — the gap is a feature request, not a bug.

The exception is a value the machine can *derive* rather than guess: a computed instant from a stated wall
time and a known zone is not a guess, and neither is a checksum. The test is whether a person would have to
verify it before acting on it.

Related: [[feedback_no_guessed_facts]] (don't state a guessed URL or path as known),
[[feedback_not_run_is_not_pass]] (a check that cannot tell success from never-ran),
[[feedback_live_values_source_of_truth]].
