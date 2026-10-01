---
name: feedback_report_the_divergence
description: When what you shipped differs from what the user approved, say so in the report — the difference is the one part they cannot see
metadata:
  type: feedback
---

When what you ship differs from what the user approved, state the departure in the report, beside the outcome. The outcome they can check; the substitution they cannot, because nothing in the result announces that something else was agreed.

Measured 2026-09-30. A plan to make a forked `/docs-relevance` proposal-only "with `disallowed-tools` enforcing it" was proposed, approved with a plain "yes", and then not shipped: the frontmatter kept `Edit, Write` for a real reason — the skill's image pipeline writes files, so the restriction would have broken screenshot work in every repo that has screenshots. The reason was sound and never reached the user. The report that followed listed the three other changes made in the same edit and omitted this one. A `/wrap-up` transcript review surfaced it hours later, as a finding rather than as a decision.

**Why:** an approval is given for a specific thing. Shipping a different thing spends trust that was granted for something else, and the better the substitute, the longer it goes unexamined. Discovering the swap later also costs more than raising it would have: by then the thing is running.

**How to apply:** when implementation reveals that the approved shape is wrong, say both halves in one breath — what was built, and what was agreed that was not. Then let them re-decide. A good reason is an argument to put in front of them, never a licence to proceed quietly. This is the same instinct as [[feedback_surface_the_gap_dont_fill_it]] applied to a plan rather than a field, and it pairs with [[feedback_honor_concrete_example]]: ask before substituting, report when you already have.
