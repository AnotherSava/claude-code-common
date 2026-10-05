---
name: feedback_dont_reask_what_you_measured
description: Having gathered the evidence a question needs, narrow the ask to what is still undecided — never pose it from scratch
metadata:
  type: feedback
---

When a procedure hands over a question and I have already collected what it takes to answer it, the ask shrinks to whatever is genuinely still open. Offer the part worth adding, confirm the set I settled, or say nothing and move on — but never re-pose the original question as though none of the work had happened.

**Why:** said on 2026-10-04, after a convention walk's v9 question reached the user unnarrowed. I had read the Makefile, the CI workflow and the project notes, built the inventory of every candidate command, written the gate and run it — then quoted the version's question verbatim, which asks whether the gate runs anything at all. The user: "if you've already collected information on possible check, and included them to the commit gate, you don't have to ask user as if you are starting from a scratch; if you have something to offer to add, you can ask about that, if not you can either confirm current set or just move along." Re-posing it spends their turn on work already done and reads as though I had not done it.

**How to apply:** state what the evidence settled and what was written, then ask only about the undecided remainder — "lint and the unit suite are in; the Release build costs minutes per commit, in or out?". Where nothing is undecided, confirm the set in one line or just carry on. A mandated verbatim quote is not an exception: quote it as required, and say which half of it the repo already satisfies, rather than letting it describe a state that is no longer true.

[[feedback_commit_gate_contents]] is this rule's worked instance for `/adopt` v9 and already said to lead with the draft; it was unmarked, so it never loaded at the moment it was needed, which is why this general form exists and why both are marked now. [[feedback_keep_your_half]] is the same reflex one step earlier — handing back a part of the task I could have finished myself.
