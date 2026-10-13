---
name: feedback_widen_what_a_human_dismisses
description: A suggestion a person can dismiss for good should be cast wide — a wrong one costs one click once, where one never made is a case nobody can act on
metadata:
  type: feedback
---

**When a suggestion is decided by a person and the dismissal is permanent, tune it for coverage rather than
precision.** The two errors are not symmetric: a wrong suggestion costs one click, once, and never returns;
a suggestion never made is a case nobody can ever act on, and nothing reports it.

**Why:** seen 2026-10-13 (trips). A merge control asks whether two stored spellings are one place. I had
narrowed its filter until it offered 41 pairs, and defended that against widening with a measurement —
matching on more spellings would add about 25 offers I could see were wrong. Presented that way it reads as
25 false positives for 1 true one. Oleg's reply was one sentence: *"you don't need to merge everything
automatically, you can leave uncertain cases for user to merge."* The 25 were never costs of the same kind —
each is one click, answered once, recorded forever — while the pair the narrow rule suppressed was an
airport and its own uncoded twin, unmergeable from either side for as long as the rule stood.

**How to apply:** before trading recall away for precision, ask what a false one actually costs the person
and whether their answer persists. Where it is one click and it sticks, widen. Where a wrong suggestion is
expensive to undo, or returns on every visit because nothing records the answer, the trade is real and
precision earns its place — so build the dismissal first, then widen onto it. The matching case for a value
nobody is asked about at all is [[feedback_surface_the_gap_dont_fill_it]].
