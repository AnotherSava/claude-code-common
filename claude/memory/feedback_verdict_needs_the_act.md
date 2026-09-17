---
name: feedback_verdict_needs_the_act
description: Saying someone broke a rule requires evidence of the act, not prose consistent with it — when the act is unobservable, ask instead of concluding
metadata:
  type: feedback
---

Reviewing someone else's work, a verdict that they **violated a rule** is the one claim that needs the
act itself as evidence. A description of the act is not the act. Ordinary review findings can rest on
reading the artifact; an accusation cannot, because the word a person chose to summarise what they did
is usually consistent with both the compliant and the forbidden version of it.

The tell is that the evidence is *prose about an action* rather than the action. A summary verb —
"re-recorded", "updated", "cleaned up", "regenerated" — names an outcome and hides the mechanism, and
the mechanism is exactly what the rule governs.

**Why:** on 2026-09-15, reviewing a peer session's change set, I read "v7 and v9 notes re-recorded" and
wrote back that it was forbidden, quoting the rule that only the writer tool may touch that file. They
had run the writer tool. The command was never in their message, so nothing I had could distinguish a
hand-edit from the sanctioned path — and I had said myself, in the same reply, that I could not see
their tree because nothing was committed. Every other finding in that review held, because each was
checked against source I could read; the one that broke was the one whose evidence was a word.

**How to apply:** before writing that something is forbidden, blocked, or a violation, name the
observation that rules out the compliant reading — a diff, a command line, a file's state. If the only
thing you have is the author's summary, ask for the command instead: "did you run X, or edit it
directly?" costs one round trip and the false accusation costs their trust in the rest of the review.
When the work is unpushed or otherwise unreadable, say that constraint applies to *your* conclusions
too, rather than only to the coverage you disclaim at the end. Related: [[feedback_no_guessed_facts]]
for asserting an unverified fact, [[feedback_read_the_evidence_you_have]] for constructing a cause
instead of reading one, and [[feedback_peer_register_not_support]] for the register a peer review is
owed.
