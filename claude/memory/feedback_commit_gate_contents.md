---
name: feedback_commit_gate_contents
description: A repo's commit gate runs its build, its lint and its tests, each where it exists; a missing linter is not invented, and dependency advisories go to Dependabot alerts, not the gate
metadata:
  type: feedback
---

A project's `.claude/commit-checks.sh` runs the build, the lint and the tests — each one where the repo has it — alongside the conventions checker. Said on 2026-09-24 in achievement-overlay, answering convention v9's question "what actually gates a commit here".

**Why:** the user's standing answer to what a gate should hold, given once rather than per repo. "Where present" is part of it: a repo with no linter configured gets no lint step, and none is invented to fill the slot.

**How to apply:** when creating or reviewing a gate — including at `/adopt` v9 — draft it from whichever of the three the repo actually has, and name the ones it lacks. Still put v9's question verbatim as `/adopt` requires, but lead with the concrete draft rather than asking from nothing. Adopting a linter where none exists is a separate one-time offer under CLAUDE.md's Best-Practice Adoption, not part of the gate. Related: [[feedback_gap_in_a_gate_is_a_fix]].

**Dependency advisories are not gated.** An `npm audit --audit-level=critical` step was added to trips' gate on 2026-11-10 and dropped the same day in favour of GitHub's Dependabot alerts. A gate step whose answer comes from a registry fails every unrelated commit, a docs-only one included, from the morning an advisory is published until a dependency is bumped, and it fails offline. The probe that tells whether a repo's Dependabot alerts are on, and how to turn them on, is in `~/.claude/learnings/gh-cli.md` under its Dependabot alerts section.
