---
name: api-explicit-over-positional
description: Context-dependent params must be named keywords (no per-context positional defaults); make invalid chains unrepresentable by type; drop ceremony terminals when chain ends are statically known
metadata:
  type: feedback
---

API-design preferences, demonstrated across the cable-channel TurnBuilder evolution (build123d-models, 2026-06):

- **When a parameter's meaning varies by context, it must be a named keyword** — e.g. a length that can be measured along the inner or outer edge is `inner=`/`outer=`, never a positional whose interpretation depends on which method it was passed to. Per-context positional defaults ("right turn leads outer, down turn leads inner") were rejected as "very confusing" even though they optimized the common case.
- **Make invalid states unrepresentable instead of validating them**: a straight-run call returns the finished solid directly, so chaining `.right()` onto it fails by type (`AttributeError`) rather than by runtime assert; the `straight=` vs `inner=`/`outer=` choice enforces "straight ⟺ no turn" in both directions (turn after straight is impossible; inner/outer without a turn fails at first use).
- **Drop ceremony when chain endings are statically known**: a builder needs no `create()` terminal if every possible last call (the entry method for the simple case, the chain methods for composed cases) can return the product itself.

**Why:** the user consistently chose call-site clarity and structural enforcement over brevity or convention-memorization, across ~6 API iterations.

**How to apply:** when designing fluent/builder APIs, propose keyword-explicit, type-enforced shapes first; reserve positional args for parameters with one unambiguous meaning (a single `length`).
