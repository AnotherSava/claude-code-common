---
name: feedback_check_where_it_is_consumed
description: A precondition is asserted on the action that depends on it, not only by a session-start check.
metadata:
  type: feedback
---

When something an action depends on is asserted only at session start, the assertion has a blind window exactly as wide as the session: what arrives in a mid-session `git pull` is missing and silent until someone opens a new one — and the session that pulled it is the one about to act. Put the check where the dependency is consumed.

**Why:** adopting convention v9 told every repo to run `python3 ~/.claude/conventions/check.py .` in its commit gate, which made the gate itself reach through a symlink that only a SessionStart hook ever verified. The user's framing was the sharper one — adoption of a newer version can change what the commit process depends on — so a version that adds a dependency is exactly when the action must start asserting it.

**How to apply:** ask which step would break without the check and put it there; a session-start copy is a sample, not the assertion. When the objection is that it would block unrelated work, look for the gate's existing report-only lane before concluding it cannot live there. Related: [[feedback_sample_level_miss_edge]], [[feedback_startup_is_not_a_poll]].
