---
name: feedback_ship_the_ladder
description: A spec's stated goal is the last rung, not the definition of done — decompose into independently shippable layers
metadata:
  type: feedback
---

When decomposing a spec, treat its stated goal as the **last rung of a ladder**, not
as the definition of done. Ask what each intermediate stage produces on its own and
whether someone would use it. Ship those as releases rather than treating everything
upstream as scaffolding.

**Why:** on the travel planner, the spec's goal was "a complete, timed route through
the city". Four independently-framed decompositions *and* two adversarial critics all
inherited that framing — they argued about ordering the work, and not one questioned
whether the intermediate outputs stood alone. They did. "Which of these places are
actually open on the specific days I'm there, holidays included" is something nobody
offers well, and treating it as scaffolding buried the highest value-per-effort piece
of the whole system behind an NP-hard solver.

**How to apply:** a ladder also fails gracefully — a rung that proves undeliverable
costs one rung, not the project. It relocates risk-retirement work too: a throwaway
spike measuring whether the data exists becomes the acceptance test of the release
that consumes it, so nothing is built to be discarded. Watch for the tell that this
is being missed: every candidate plan agreeing on what "done" means while disagreeing
only about sequence. See [[feedback_no_premature_abstraction]] for the opposite
failure — building structure before the value is proven.
