---
name: feedback_reread_the_whole_procedure
description: When one step of a multi-step procedure goes stale, re-read the whole document as a sequence — a single moved file usually falsifies several steps, and only one gets flagged
metadata:
  type: feedback
---

When something a procedure depends on moves or changes, do not patch the line you were pointed at. Re-read the whole document **as a sequence**, because one relocated file typically falsifies several steps and only one of them is the one somebody noticed.

The sharpest case, and the one that is invisible when patching a single line: **a procedure's step-N output is often step-M's baseline.** Change the input in one and not the other and the two stop being comparable — the operator meets a discrepancy the procedure invented for itself, at the worst possible moment, because the steps that compare outputs are usually the verification ones that run right after the irreversible part.

**Why:** on 2026-08-26 `identity-check.py` and its manifest moved into a different repo. One session flagged §3.3 of a cutover runbook as stale. Re-reading the document end to end found **four** falsified passages: §3.3, plus §0.1 and §2.1 — which pointed at the old path and whose outputs are explicitly compared to each other — plus a troubleshooting paragraph that now attributed a count mismatch to the wrong cause. Three of the four were unreachable from being told about the first.

**How to apply:** when told a document is stale in one place, grep it for every mention of the moved thing, then read it in order and ask of each step: what does this consume, what does it produce, and which later step consumes *that*? Update the expected outputs by **running the commands**, not from memory ([[feedback_write_the_procedure]]). In a document describing a migration, also say which line becomes true at which step, and mark explicitly any line that is correct as it stands — a stale row is never a reason to apply its neighbours early, and a reader tidying up will otherwise assume it is.
