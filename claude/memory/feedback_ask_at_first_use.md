---
name: feedback_ask_at_first_use
description: bootstrap a permission list by asking at first use rather than requiring it configured up front; design the ask, and check where the prompt can actually be seen
metadata:
  type: feedback
---

Prefer bootstrapping a permission list by asking at the moment of first use over requiring it to be configured up front.

**Why:** offered a hand-maintained allowlist and a click-to-add affordance, the user proposed a third option (2026-08-31): start empty, and ask when a request arrives for something not on the list. It removes the setup step entirely, and it is also the safer default — a project that is never asked about never carries a grant at all, so the off state is genuine rather than nominal. A config field plus documentation puts the burden on the user *and* invites them to pre-authorise things they will never use.

**How to apply:** when a feature needs an allowlist, default it empty and design the ask, rather than shipping a config field and explaining how to fill it. Two things to get right: the answer must be recordable so the same question is not asked twice, and the prompt has to be raised somewhere it can actually be seen — the machine that needs the permission may be precisely the one nobody is sitting at, which can mean asking on a different machine from the one the grant applies to. Related: [[feedback_surface_the_gap_dont_fill_it]].
