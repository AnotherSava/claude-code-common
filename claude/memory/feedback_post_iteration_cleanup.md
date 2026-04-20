---
name: Post-iteration cleanup audit
description: After long iterative debug/optimize sessions, proactively audit accumulated changes and propose removing things that didn't help
type: feedback
---

After an extended iterative session — debugging, optimizing, trying multiple hypotheses — do a cleanup pass before committing. Proactively identify changes that were added mid-investigation but didn't end up helping, and propose removing them. Don't leave disproven experiments as code cruft.

**Why:** In one long area-select perf/cursor iteration the user said: *"if there are other changes you performed during our iterative process, that didn't help, but you kept them anyway - maybe it's time to consider removing them - unless they add some value."* That direct prompt uncovered a `Capture = true` call in `Show()` that had stuck around from a disproven smoothness theory — two other theory-driven changes had been organically reverted during the session but one lingered. The user wanted it gone before the commit.

**How to apply:** When a `/commit` is invoked after a session with multiple hypotheses tested (especially performance/UX iteration or bug chasing), scan the diff for additions motivated by theories that later turned out wrong. Call each one out with its original motivation and current justification. Remove if it no longer earns its place. Do this as a natural part of commit-prep, not only when the user asks.
