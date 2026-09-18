---
name: feedback-encode-the-determined-answer
description: When a skill's mandated question has an answer already determined by the artifact, say so and encode the heuristic rather than asking that question every run
metadata:
  type: feedback
---

A skill that gates on a question you must put to the user is right to have the gate, and wrong to charge for it twice. Where the answer is already determined by something on disk — the file's path, its extension, which directory it sits in — the question buys nothing, and asking it again next run buys nothing again.

**Why:** on 2026-09-17 the `docs-style` skill opened with "who reads this, and what for", asked as its own first step about three files whose paths decided it. The reply was not an answer but an instruction: add heuristics so it stops asking. This case sits between two existing rules and is neither of them. [[feedback_follow_skill_instructions]] says never skip a numbered step, so simply not asking was never available. [[feedback_fix_skills]] covers a skill that *fails*; this one worked exactly as written.

**How to apply:** when a skill asks you something and you notice the answer was decidable from the artifact in front of you, say that in the same turn — name what decides it. Then follow [[feedback_no_unprompted_skill_edits]] for the edit itself: make it when the user has asked, offer it when they have not. A user who answers the skill's question with a rule instead of an answer ("add heuristics so you don't ask each time") has asked. Write the heuristic as a named determinant plus a line saying to ask only where it does not apply, and do not widen it past the cases you can name.
