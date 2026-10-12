---
name: feedback_threshold_serves_the_decision
description: Derive a magnitude threshold from the decision it serves and defend it with the measured gap between the populations it separates; a new signal widens a match rather than overturning one
metadata:
  type: feedback
---

Pick a magnitude threshold from the decision it serves, not from an intuition about its unit, and defend it with the measured gap between the two populations it must separate.

**Why:** on 2026-10-11 a place-matching rule in the trips project got a 1.5 km radius, chosen as "walking distance". The question it actually served was whether a booked leg was missing between two places, which no walk settles — "do we want to force user to add transport between airport and hotel, where public transport works just fine". Reframed as one urban area, the number became 25 km: bounded below by the pairs that had to match (12 km, 22 km) and above by the shortest journey in that data which genuinely needed a booking, about 100 km.

**How to apply:** state the decision before choosing the number, then name the largest same-class separation and the smallest different-class one; a threshold with no gap between those two is doing a job it cannot do. Add a new signal as one more way to agree — overruling an existing match needs the new signal to be strictly more authoritative about that same question, which the 1.5 km version was not: it broke pairs the old rule had right. Related: [[feedback_no_guessed_facts]] for the number itself, and [[feedback_lead_with_the_rule]] for how to present one.
