---
name: feedback_ask_alongside_not_before
description: Don't hold implementation to ask a question whose answer wouldn't change what gets built — ask alongside delivering
metadata:
  type: feedback
---

When a fix is verified and complete, don't hold implementation to ask a question whose answer
wouldn't change what gets built. Ask alongside delivering it, not before.

**Why:** on achievement-overlay issue #7 I recommended replying to the reporter before implementing,
on the grounds that if his game folder wasn't covered by `gamesPaths` the fix would do nothing for
him. Challenged on that recommendation, it didn't survive: his answer would only decide whether *he*
benefits, not what the code should do — and his own report already implied the precondition held.
Gating a verified fix on it would have delayed the work for nothing, and the reply reads better
written about a change that exists than one that is merely proposed.

**How to apply:** ask "would a different answer change what I build?" If no, build it and ask in the
same message. Reserve blocking on a third party's answer for when the design genuinely forks on it —
and then say which fork each answer selects, so the question is visibly worth the wait. Distinct from
[[feedback_check_the_limit_is_real]] (check the system before settling for unverified) and from the
Self-Sufficiency rule about not asking the user to run things: this one is about *sequencing* work
behind someone else's reply.
