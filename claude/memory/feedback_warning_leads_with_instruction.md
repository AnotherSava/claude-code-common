---
name: feedback_warning_leads_with_instruction
description: A warning says what to do first and why second, with the reason load-bearing for the instruction
metadata:
  type: feedback
---

A warning tells the user **what to do** first and **why** second. The reason has to be load-bearing
for the instruction rather than decoration beside it.

**Why:** the two halves fail independently, and both failures look fine in isolation. A warning with
no instruction states a fact and never asks for anything. A warning whose reason is a tautology asks
for something and justifies it with nothing, so it reads as filler and gets skipped.

**How to apply:** write the imperative, then a reason a reader could not have supplied themselves. If
the reason is something they already know, it is not a reason — cut it and find the real one. Test the
pair: does the reason explain why the instruction has to happen *now*, or in *that order*?

Real case, one notice, two bad drafts:
- *"Read each part before you send this file. Whoever you send it to can see everything in it."* —
  instruction fine, reason a tautology.
- *"Attaching this to a GitHub issue publishes it: … GitHub uploads it the moment you drop it in."* —
  reason excellent, no instruction at all.
- Correct: both, in that order. "GitHub uploads it the moment you drop it in" is precisely *why*
  reading has to happen beforehand, which is what makes it a reason rather than a fact.

Related: [[feedback_sentence_case_ui]], [[feedback_minimal_ui_chrome]].
