---
name: feedback_mark_the_container_not_every_item
description: A scope marker on a container says where its work must happen, not that every item inside is bound — don't withhold it because one part is portable
metadata:
  type: feedback
---

When a marker classifies a container — a memo, an issue, a ticket, a task list — it says where the work has to happen. It is not a claim that every line inside it is bound. Don't withhold the marker because one item is an exception.

2026-09-15, tagging memos with a newly built `platform:` field. Two candidates: one whose fix cannot be verified on this box although the audit part runs anywhere, and one whose four work items are three Windows and one explicitly portable — the portable one being the cheapest and listed first. I analysed both, wrote that tagging the second "mislabels its cheapest item", and handed the call back with both untagged. The answer was "mark both as windows".

**Why:** the mixed case already had a mechanism, built in the same change — picking a tagged memo tells the session to do the portable part here and route the rest to the machine that can act. The tag was withheld on exactly the case it had been designed for. That is [[feedback_use_the_tool_you_built]] showing up in a classification rather than in a workflow.

**How to apply:** mark by where the work has to happen, and reach for the exception only when the marker would be wrong for the *majority* of the thing being marked. [[feedback_surface_the_gap_dont_fill_it]] governs a field a human must **vouch** for — a provenance, an attestation, a sign-off — and a classification derivable from the item's own text is not one of those. Deriving it is my half of the task ([[feedback_keep_your_half]]); what goes back to the user is the marked result, not the question.
