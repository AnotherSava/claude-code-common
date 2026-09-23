---
name: feedback_gap_in_a_gate_is_a_fix
description: A blind spot in a gate the project already runs gets the gate extended, not a memo — a parked class of defect is rediscovered and re-filed instead of closed
metadata:
  type: feedback
---

When the defect you noticed is a **blind spot in something the project already runs** — a commit
check, a convention rule, a lint config, a CI job — propose extending that thing. Do not offer to
park it.

**Why:** a memo defers an idea nobody is working on yet, and a class of defect is not that. It will
present itself again, and the next review rediscovers it and files it a second time, so the backlog
grows an entry per encounter while the hole stays open. Extending the gate closes every future
instance at once. This is the opposite of the per-objection guard
[[feedback_read_only_review_loop]] warns about: that one adds a new mechanism for each complaint,
this one teaches an existing mechanism to see what it was already meant to cover.

Instructed 2026-09-23. `claude/CLAUDE.md` had just gained a sentence extending the co-tenancy naming
rule to DNS zones, and `cotenant-service-names.py` read only compose files, so the new half had
nothing enforcing it. The offer was "Memo that?"; the answer was "fix".

**How to apply:**
- Name the gate in the proposal. "The commit check reads compose files only" is what makes it a fix
  rather than a complaint — and it is usually the whole of the work.
- The test is whether a place to put the check **already exists**. Where it does not, building one
  for a single observation is the premature machinery
  [[feedback_no_permanent_logic_for_one_time]] rules out, and a memo is right again.
- `wrap-up/SKILL.md` carries this rule for the findings its own review produces. This memory is the
  same rule everywhere else, because the offer is made far more often from ordinary work than from
  a wrap-up, and nothing there said it.
- Extending a rule that other repos have already adopted is not a free edit — a stricter check is a
  new convention version, while an edit in place is only for detecting the same requirement more
  accurately. `claude/conventions/authoring.md` owns that split.
