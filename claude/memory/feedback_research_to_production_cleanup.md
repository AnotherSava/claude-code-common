---
name: Captured the lesson, drop the code
description: When research-stage code transitions to production, delete functions whose rationale is preserved in docs — the docs are the memory
type: feedback
---

When refactoring research/experimental code into production, aggressively delete helper functions and alternative implementations whose rationale is captured in docs (FINDINGS.md, ALGORITHM.md, ADRs). Don't keep "for future iterations" — that's cargo-culting research stage.

**Why:** During the reconstruct module refactor (2026-05-11), several utility functions survived the initial port purely because they had been useful during development — `edge_contact_length` (disproven datum metric), `cap_depth` (provisional world-frame variant), `patch_bbox` (debug helper), `make_local_basis`/`to_local_2d` (provisional frame helpers). User's principle: *"Each of these survived only because it was useful during development. Once a function isn't on a code path AND its rationale is preserved in docs, keeping it is cargo-culting research stage. The docs are now the memory; the code should reflect the current algorithm."*

**How to apply:** During clean-code on a research→production transition, for every defined-but-uncalled function ask: is its rationale already captured in docs? If yes, delete; the doc keeps the lesson. Exception: debug helpers worth keeping somewhere can move to a `_debug.py` or `tmp/<topic>_dev/`, not the public module surface.

**The same trim applies to the record, not just the code.** A memory written from temporary instrumentation keeps only the claim that outlives the tool — drop its name, its run window, the events it was wired to and its totals, unless a number is the evidence the claim rests on. Real case (2026-09-02): a retired hook-payload dumper's first memory draft recorded the dumper, three months of capture, four wired events and per-event counts; the user's *"do we even need to keep memory about some temporary debug hooks"* was right, and one sentence survived — that a shipped code path had never executed — with the counts kept only as its grounds.
