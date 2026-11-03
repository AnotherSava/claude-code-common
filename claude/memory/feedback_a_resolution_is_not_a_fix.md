---
name: feedback_a_resolution_is_not_a_fix
description: "next time I should X" carries into no later session; fix what the next session sees at the moment it decides
metadata:
  type: feedback
---

A slip that ends in "next time I should X" has fixed nothing. No later session inherits the conclusion: it starts fresh, meets the same trigger in the same text, and has the same reason to take the same shortcut. The fix is a change to what that session sees at the moment it decides — the message that triggers it, the skill it runs, or a gate that refuses the wrong path.

**Why:** 2026-11-03, a peer's push notice asked a session to run `/pull`. The clone was already current, so the session checked by hand and skipped the skill's last step, which tells the dashboard the turn left nothing behind; the row settled DONE instead of CLEAN. The session concluded "run the skill next time", and the user asked why it expected its behaviour to change. It had no reason to: the notice text was what had to change, and it was routed to the session that owns it.

**How to apply:** when a diagnosis of your own slip ends in a resolution, name the artifact the next session will read at that decision point and propose changing it — routed to its owner when it lives in another repo. A memory line is the weakest carrier of the options, since it competes for attention with the instruction actually in front of the reader; prefer the triggering text or the skill. Related: [[feedback_follow_skill_instructions]], [[feedback_fix_skills]].
