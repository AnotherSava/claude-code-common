---
name: Captured the lesson, drop the code
description: When research-stage code transitions to production, delete functions whose rationale is preserved in docs — the docs are the memory
type: feedback
---

When refactoring research/experimental code into production, aggressively delete helper functions and alternative implementations whose rationale is captured in docs (FINDINGS.md, ALGORITHM.md, ADRs). Don't keep "for future iterations" — that's cargo-culting research stage.

**Why:** During the reconstruct module refactor (2026-05-11), several utility functions survived the initial port purely because they had been useful during development — `edge_contact_length` (disproven datum metric), `cap_depth` (provisional world-frame variant), `patch_bbox` (debug helper), `make_local_basis`/`to_local_2d` (provisional frame helpers). User's principle: *"Each of these survived only because it was useful during development. Once a function isn't on a code path AND its rationale is preserved in docs, keeping it is cargo-culting research stage. The docs are now the memory; the code should reflect the current algorithm."*

**How to apply:** During clean-code on a research→production transition, for every defined-but-uncalled function ask: is its rationale already captured in docs? If yes, delete; the doc keeps the lesson. Exception: debug helpers worth keeping somewhere can move to a `_debug.py` or `tmp/<topic>_dev/`, not the public module surface.
