---
name: feedback_removal_scopes_to_the_region
description: "Remove X from region R" scopes to R, not to X — enumerate the region and ask what stays, rather than deleting the named item and waiting
metadata:
  type: feedback
---

When the user asks for something to be **removed from a named region**, the thing they name is an example of what is in that region, not the boundary of the request. Delete only the named item and the same instruction comes back.

Real case 2026-09-21 — three rounds for one intent: *"do not create a separate area on the top of the right column with plan item details"* → removed the candidate summary → *"I still see some plan item information on the top"* → removed the message heading → *"remove part altogether, move accept/reject to the left column"*. What was wanted throughout was *nothing above the trip*, which the first message already said.

**Why:** the region is what they are looking at, so they describe it by whatever is most salient in it. They have not inventoried it either, so a literal reading is not even a faithful one — the third round dropped a control I would never have proposed dropping, and they accepted a real loss of function (no way to choose the trip) to get the region clean. That is not a decision a piecemeal reading would ever have reached.

**How to apply:** on a removal scoped to a region, enumerate the region's contents, label them, and ask which stay — do not delete the named item and wait. Doing exactly that settled it in one round: a labelled diagram of the five parts with the cost of removing each, through `AskUserQuestion`, and the answer was the option I had ranked least likely.

This narrows [[feedback_honor_concrete_example]], which says to implement the user's literal example rather than a generalisation of it. That holds for what to **build**; for what to **remove from a region**, the literal reading under-delivers and the generalisation is the request. Related: [[feedback_fix_the_class_not_the_instance]], the same instinct where the set is already enumerated somewhere and only has to be found.
