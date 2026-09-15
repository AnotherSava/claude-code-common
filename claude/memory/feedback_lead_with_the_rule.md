---
name: feedback_lead_with_the_rule
description: When a request names a value but you implement a rule that derives it, say so in the first sentence of the report — the value alone reads as hardcoded
metadata:
  type: feedback
---

When a request names a specific value and you implement a **rule** that produces it, say so in the **first** sentence of the report, not the second.

2026-09-15, the Work intensity chart: asked to "not show data before Jul 27 (almost no token data)", I built a leading trim — drop the oldest weeks holding less than one bar's worth of tokens — which derives Jul 27 from that user's own history and would derive a different week for anyone else. The report opened "The history now starts at the week of Jul 27" and named the rule in the sentence after. It still cost a round trip: *"wait, this date shouldn't be hardcoded - it might be different for different users; what criteria could we use?"* — describing, almost word for word, what the code already did.

**Why:** the first sentence is the one that gets acted on, and a bare value in it reads as the *input* rather than the *output*. Being right in the second sentence does not undo that, and the cost lands on the reader, who now has to either take the correction back or read the diff to settle it.

**How to apply:** "the rule trims leading weeks under 1M tokens, which on your data starts the history at Jul 27" — mechanism first, value as its consequence. The same shape covers a threshold, a default, a cutoff, a computed limit. It is not hedging or padding: it is one clause, and it is the clause that says the number is not stored anywhere. Related: [[feedback_no_guessed_facts]], [[feedback_warning_leads_with_instruction]].
