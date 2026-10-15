---
name: feedback_ask_only_what_changes_the_build
description: Don't propose asking an issue reporter or other outsider for a fact whose answer would not change what gets built
metadata:
  type: feedback
---

Don't propose asking an issue reporter (or anyone outside) for a fact whose answer would not change
what gets built. Before drafting the question, ask whether either answer leads to a different design;
if the right build covers both, build it.

**Why:** 2026-10-14, I proposed asking an issue reporter which tool produced their setup; the owner
replied that if our wizard handles that case correctly, their current tool does not matter.

**How to apply:** research questions to an outsider get the same test as
[[feedback_dont_reask_what_you_measured]] — only the undecided remainder that changes the plan.
