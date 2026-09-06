---
name: feedback_fix_the_part_not_the_whole
description: When the user objects to one element, fix that element — don't delete the construct containing it
metadata:
  type: feedback
---

When the user objects to one sentence, field, or element, the **flagged part is the scope of the
correction**. Fix that part; do not remove the construct containing it.

**Why:** deleting the enclosing whole silently discards things the user never objected to, and they
then have to notice the loss and ask for it back — which reads as two mistakes rather than one, and
costs a round trip on something that was already right.

**How to apply:** locate the exact span the objection covers, edit that span, and leave its
neighbours alone. If removing the part leaves the construct incoherent, that is a signal to *rewrite*
the construct, not to drop it — and worth saying so rather than deciding silently.

Real case: a two-sentence UI notice. The user flagged the second sentence as an obvious tautology; I
deleted the whole line, taking the first sentence with it — the instruction that made the notice
actionable — and had to be asked why it went. Applies equally to prose, config blocks and UI copy.

Related: [[feedback_post_iteration_cleanup]], [[feedback_no_unsolicited_data_fixes]].
