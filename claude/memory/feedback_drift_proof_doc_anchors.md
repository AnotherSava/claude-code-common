---
name: feedback_drift_proof_doc_anchors
description: A doc reference to a position or range must be anchored open-ended — a line number or today's last item reads as exhaustive after it stops being
metadata:
  type: feedback
---

When a document points at a **position or a range** rather than a value, anchor it on something that cannot move. "`APP_CONTAINER` onward" and "every key below it" survive an append; a line number and the name of the current last item do not.

**Why:** in a `config/publish.env` header warning that sourcing the file aborts the shell, I wrote "every key BELOW it, `APP_CONTAINER` through `VHOST_SRC`" — accurate, because `VHOST_SRC` was the last key. Append one key after it and the sentence still reads as exhaustive while quietly understating the damage, in a file whose entire purpose is to stop someone being misled. I had already rejected the line number as drift-prone and then reached for a terminal name with the same failure mode and no number in it to make it obvious. My own edit demonstrated the half-life in the same turn: it moved `BUILD_SERVICES` from line 37 to line 46.

**How to apply:**
- Anchor on what is **stable** (the first item, a named marker) and let the far end run open: "X onward", "every … below", "the keys after X".
- Two forms rot on the same trigger — someone appending: a **line number**, and a **terminal name** used as a bound. Avoiding the first is not avoiding the second; the terminal name is the sneakier one because it carries no digits to flag it.
- The test: what does someone appending an item have to remember? If the answer isn't "nothing", re-anchor.
- Evidence in a peer's message is not proposed wording. An explicit enumeration may be offered to prove a mechanism — pasting it in as the fix imports a bound that was never meant to be durable.

Sibling of [[feedback_cite_the_source_not_the_count]], which owns the **count** form ("the seven keys below") and its different fix — cite the command that yields the number. Both are references that are correct when written and decay with nobody touching them; this one is about where a range *ends*, not what a number *says*. Cousin of [[feedback_live_values_source_of_truth]] (citing a live value from a stale snapshot).
