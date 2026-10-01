---
name: feedback_mirror_carries_the_exceptions
description: a short form of a rule stated in full elsewhere must carry its carve-outs, or a reader working from the summary alone suppresses what the rule allows
metadata:
  type: feedback
---

When you write a short form of a rule that lives in full somewhere else — a README feature bullet, an Out-of-scope line, an index blurb — carry the rule's exceptions into it. A mirror keeping only the prohibition reads as absolute, and whoever works from the mirror never sees the full text.

**Why:** the exception is often the common case rather than the edge. The `docs-relevance` rule "report a doc gap in an upstream-owned file and edit nothing" has two carve-outs — the gap belongs to a change the user carries on their own branch, or to an issue they already raised — and in the user's own forks the own-branch case is the normal one. Both short forms dropped them, so an agent reading either would have suppressed a memo the rule permits.

**How to apply:** after writing or syncing a summary of a rule, read it against the full text for each "unless", "except" and "two exceptions". Where the carve-out will not fit, say what the summary omits rather than stating the bare prohibition. Related: [[feedback_state_the_enforcement_reach]].
