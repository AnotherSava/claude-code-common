---
name: feedback_verify_peer_conclusions
description: A peer's evidence and the inference built on it fail independently; re-derive the conclusion rather than checking the quotes
metadata:
  type: feedback
---

When another session hands you findings, its evidence and its conclusion fail independently —
verify both. Measured 2026-09-29: a peer's three doc quotes about permission scopes checked out
verbatim against the source page and its measurements of which settings files existed were exact,
while the conclusion was the one candidate that same evidence excluded. It read a session-scoped
grant as surviving; the page it quoted puts that option on a *prompt*, and its own measurement was
that no prompt appeared.

**Why:** checking the quotes feels like checking the claim, and it is the cheap, satisfying half.
An accurate evidence section raises confidence in the inference instead of testing it, so a wrong
conclusion arrives better defended than a sloppy one. The same peer had already sent one causal
claim that dissolved on measurement — "it ran only after the rule was added", with no such rule
anywhere on the machine — and that one reached two committed files as a prescribed remedy before
it was caught.

**A peer's verification stops at their own module boundary.** Measured 2026-10-03: a peer reported
that a hand-attached terminal tab could have a reading credited to the wrong row, having traced how
the row was *resolved* — correctly — and assumed what became of that resolution downstream. The step
after it refused the credit outright, on a test the peer never read, so the hazard did not exist; it
was already written into a README as a stated hazard and came back out a round trip later. Their own
retraction named the shape: "I verified the resolution half and asserted the rest." Ask which stage
the peer actually read, and trace the stages after it before putting any of it in prose.

**How to apply:** re-derive the conclusion yourself before recording it, and say which parts you
verified and which you re-derived. Where it stays open, record the candidates and what excludes
each rather than adopting the peer's pick — see [[feedback_no_guessed_facts]] and
[[feedback_assumptions_vs_facts]]. A peer offering to run a probe is not a shortcut: check the
probe can discriminate between the candidates first, since a confounded one answers a different
question confidently. [[peer_messaging]] covers the sending side.
