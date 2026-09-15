---
created: 2026-09-15 09:59:29
---

# Second pass: decide {always} for the dozen arguable global memories

The 2026-09-15 promotion pass marked ten of the 126 unmarked memories {always} and explicitly left about a dozen as arguable, never settled.

The test to apply to each is the one the first pass used: would anything prompt me to look this up? A memory whose situation is its own trigger (a platform note, a CSS specific, a Notion/Telegram reference) stays findable and needs no marker. A general working rule has no trigger, so unmarked it never fires at all.

The dozen flagged as arguable, by index key:
  feedback_uncommitted_is_not_delivered
  feedback_ask_alongside_not_before
  feedback_reread_the_whole_procedure
  feedback_extend_what_you_built
  feedback_compare_to_current_state
  feedback_dont_recheck_known_answers
  feedback_assumptions_vs_facts   (overlaps feedback_no_guessed_facts, which is already {always})
  feedback_ship_the_ladder
  feedback_hold_the_stated_objective
  feedback_no_unprompted_skill_edits
  feedback_eliminate_bug_class
  feedback_cross_platform_scripts

Mechanics: append ' {always}' after the link in claude/memory/MEMORY.md, then run python3 claude/scripts/render-memory-index.py. Each promotion costs roughly 200 bytes of every session's context; the ten already promoted added 2,165 bytes (67.5 KB -> 69.6 KB). Quote the new total when proposing, as the first pass did.
