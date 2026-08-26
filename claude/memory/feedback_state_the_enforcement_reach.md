---
name: feedback_state_the_enforcement_reach
description: A document citing a check must not state a conclusion broader than the check delivers; naming what the check cannot see is part of describing what it does
metadata:
  type: feedback
---

When a document points at a real check — a test, a linter, a validator — its conclusion must not reach further than the check does. Naming what the check **cannot** see is part of describing what it does, not a caveat to append if there is room.

The failure is quiet because the sentence is usually *technically* true of its subject. A careful reader tracks the scope from the preceding clause; a skimming reader takes the conclusion as absolute, and stops verifying — which is precisely the behaviour a citation like "and X enforces it" produces on purpose. An overclaim is therefore worse than no claim, because no claim leaves the reader checking.

**Why:** two instances in one session on 2026-08-26, in one repo. A README said nothing outside a directory names *a host, a hostname, a DNS provider, a credential or an email address* — "and `tests/host.py` enforces that rather than asking." The test enforced **one** of the five, across four directories, and the claim was falsified in that repo's own tree in four places. Separately, a contract said a hostname "cannot exist in one list and be missing from another" one sentence after naming the two lists the test cross-checks — unscoped, and the day before, a copy of one of those files living outside the repo had made it absolutely false.

**How to apply:** after writing any sentence of the form "X enforces this", go read X and list what it actually inspects. Then scope the conclusion to that set explicitly ("one of *these* lists"), and add the boundary as a permanent sentence — a copy outside the repo, a path outside the walked directories, a case outside the matched pattern. Date nothing: the reach of a check is a durable property, not a transitional one, so this needs no removing later. Related: [[feedback_guard_the_input_not_the_output]] (a guard that cannot observe the failure it names) and [[feedback_not_run_is_not_pass]] (a check that cannot distinguish passing from never running).
