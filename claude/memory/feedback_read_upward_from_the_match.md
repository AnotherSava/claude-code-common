---
name: feedback_read_upward_from_the_match
description: A grep shows what follows a definition, never what precedes it — read upward before calling a value unexplained or a list unaudited
metadata:
  type: feedback
---

A grep lands you *on* a definition and shows you what **follows** it. A definition's rationale conventionally sits **above** it, so an audit driven by a grep hit reads the values with their reasons cut off — and then re-derives, often wrongly, a decision the file already records.

**Why:** the blindness is created by the instrument, not by the file. The rationale was present, committed, and written in prose aimed at exactly the question being asked; the forward-only context window is what hid it. That makes it invisible in the ordinary way — nothing looks missing, because the output looks complete.

Measured 2026-09-14, auditing `PUBLISHABLE_PROJECTS` in the dashboard's capture library: `grep -A25` returned the tuple and the functions below it. The twenty lines directly above the match already named every entry's repository, recorded one of them as a private repo kept on the list by its owner's explicit clearance, and explained another as a row rename rather than a project. Two findings went to the user that the file had answered in prose they had written into it three days earlier.

**How to apply:** pass `-B` as well as `-A` when the match is a definition, or Read the file around the line instead of grepping it. The cost is asymmetric — a few extra lines of context against a question the user has to answer twice. [[feedback_check_the_limit_is_real]] is the same reflex one level up: check whether the thing is already handled before reporting it as open.
