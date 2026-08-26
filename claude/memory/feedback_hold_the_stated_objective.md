---
name: feedback_hold_the_stated_objective
description: Keep the user's stated objective as the deliverable, and audit any framing inherited from another agent or doc before repeating it
metadata:
  type: feedback
---

Twice in one session I restated the goal in weaker terms than the user set it. First I adopted a counterpart
agent's phrase — "unpinning is a convenience, not a fix for anything broken" — and repeated it to the user
without checking it against costs I had myself measured that same hour: a production outage traced to the
version split, three misdiagnoses of the same class in twelve days, and a permanently non-standard commit
invocation. Then, having found a fix, I described the Node 24 move as "optional and trivial later" when
aligning the two projects on one Node version was the entire reason the investigation existed.

**Why:** a second-hand framing arrives pre-argued, so it feels like agreement rather than a claim that still
needs testing — especially when it is *modest*, since understatement reads as rigour. And once a means is
found, the means quietly becomes the deliverable while the end gets demoted to a follow-up.

**How to apply:** when a counterpart, a document, or a memory supplies the framing for work in progress —
particularly one that downgrades its importance — check it against your own evidence before repeating it to
the user. When you find a fix, restate the *original* objective and say plainly whether it is now met, rather
than describing the fix and leaving the goal implicit. Related: [[feedback_ship_the_ladder]] — decomposing a
goal into independently shippable rungs is right; relabelling the goal itself as optional is not.
