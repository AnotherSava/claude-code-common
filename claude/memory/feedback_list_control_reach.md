---
name: feedback_list_control_reach
description: A control that acts on several rows names how far it reaches and sits under the list; with cheap undo it overwrites rather than guarding filled rows
metadata:
  type: feedback
---

A control that changes more than the row it sits on has to say, in its own label and position, how far it reaches.
Three corrections on one hours editor, 2026-11-16 (trips repo):

- **The label names the direction and the extent.** "Same as above" on an empty row, which filled every empty row
  from the last filled one down to itself, drew "doesn't hint that it will fill all rows up to this". It became
  "Copy to days below" on the filled row, the source of the copy.
- **A qualifier protecting rows the user can fix anyway is noise.** "Copy to empty days below" drew "why empty?".
  Nothing was saved until OK and Cancel discarded the draft, so the natural order is copy first, then edit the
  exceptions; the button overwrites every later day.
- **A control acting on the whole list sits beneath the list, not beside its first row.** A "Change" placed inline
  after the first line of a per-day list read as editing that day only. It moved under the list. A single-line value
  keeps its control inline.

**Why:** the user reads scope from wording and placement before clicking; a control that hides its reach either
surprises them or goes unused.

**How to apply:** for any bulk or multi-row action, put the scope in the verb phrase ("to days below", "to all"),
anchor it on the row it copies from or under the group it changes, and skip safety qualifiers when the whole edit is
undoable before saving. Related: [[feedback_minimal_ui_chrome]], [[feedback_no_underline_links]].
