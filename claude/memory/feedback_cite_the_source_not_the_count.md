---
name: feedback_cite_the_source_not_the_count
description: A document that quotes a count of things that change is wrong on a schedule; cite how to read the number from the source of truth instead
metadata:
  type: feedback
---

When a document quotes a **number that tracks a changing set** — how many tenants, hosts, targets, entries — it is not merely at risk of going stale, it is wrong on a schedule. Cite the source of truth and how to read it, not the value.

The trap is that the number is *correct when written*, so nothing looks wrong at review, and reviewing it again later requires knowing the set changed — which is exactly what the reader consulting the document does not know.

**Why:** on 2026-08-28 a cutover runbook told the operator "if the declared count is not 8, **stop** and explain it before continuing". Eight was correct against the committed manifest. A fourth tenant was already staged in the working tree — uncommitted, so the sentence was true at that instant and would become a false *stop* instruction the moment that tenant was committed, for an entirely ordinary and correct reason. The instruction would have halted a cutover using a document that was itself out of date. Nearby, a contract section claiming "all three tenants reach the gate" was in the section whose whole subject is *not overstating enforcement*.

**How to apply:** replace the value with the property, or with the command that yields the value. "Every tenant that publishes reaches it" instead of "all three tenants reach it". "The count must agree with the manifest — read it with `python3 -c ...`" instead of "the count must be 8". Where an example number genuinely helps a reader recognise the output, label it as an example that moves, and put the assertion on the comparison rather than the literal. Leave **dated historical records** alone: "verified on 2026-08-27, all three tenants asserted" is a claim about a moment and stays true. The test is whether the sentence is making a claim about *now*. Related: [[feedback_state_the_enforcement_reach]] (claiming more than a check delivers) — this is its sibling, a claim that decays without anyone touching it. See also [[feedback_drift_proof_doc_anchors]] for the same decay in a *positional* reference — where a range ends, rather than what a number says.
