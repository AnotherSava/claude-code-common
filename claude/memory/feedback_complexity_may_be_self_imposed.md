---
name: feedback_complexity_may_be_self_imposed
description: When work balloons around a constraint, check the constraint is real — and evaluate the user's actual proposal, not a maximal version of it
metadata:
  type: feedback
---

When a task starts ballooning, check whether the difficulty is in the problem or in something **I**
put there. Two shapes of this, both seen in one session.

**A constraint I shipped, treated as immovable.** Two workflows went into designing a
content-corroboration rule to work around a limit — until the user asked "if stripping the zeros by
hand gets the right result, why is it hard on our side?". It wasn't: the flag being worked around had
exactly one production use, and the whole question was policy, not mechanism. A user asking "why is
this hard?" is often pointing at a constraint that is a decision rather than a fact.

**A proposal inflated by a subagent, then relayed.** Asked to design a feature the user had already
scoped concretely (four files the app already identifies), a workflow produced a maximal version — a
redaction subsystem, a game picker, a consent UI — priced *that*, and recommended against building
it. I relayed the recommendation. The user's actual proposal measured ~15 KB and was reviewable; the
objections were all to the inflation.

**How to apply:**
- Before designing around a limit, name where it came from. If it is a decision, it is on the table.
- When delegating a design, evaluate the answer against **what the user asked for**, not against the
  brief the subagent gave itself. A recommendation-against is suspect when the thing rejected is
  bigger than the thing requested.
- Measure the user's version before arguing about it. Sizes, counts and a look at the real files
  settle this faster than any amount of reasoning.

Related: [[feedback_no_premature_abstraction]], [[feedback_no_permanent_logic_for_one_time]].
