---
name: feedback_warning_leads_with_instruction
description: A warning says what to do first and why second, with a reason that actually forces the instruction
metadata:
  type: feedback
---

A warning tells the user **what to do** first and **why** second. The reason has to be what forces the
instruction rather than decoration beside it.

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

Third failure mode, found 2026-09-14: **a reason that names the mechanism instead of the consequence.**
Handing over a destructive command, I wrote *"disconnect the VPN first: the command matches by marker, so
while connected it deletes the live rule too."* Every word true, and the user ran it while connected
anyway — "deletes the live rule" is unpriceable to anyone who does not already model the mechanism. The
actual cost was that all name resolution on the machine stopped. Give the cost, not the internal step that
produces it: *"while connected, this takes DNS down for the whole machine."*

Related: [[feedback_sentence_case_ui]], [[feedback_minimal_ui_chrome]],
[[feedback_live_values_source_of_truth]].
