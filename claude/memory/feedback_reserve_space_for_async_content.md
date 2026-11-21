---
name: feedback_reserve_space_for_async_content
description: Content that arrives after an async step (a lookup filling a field, a row revealed by a result) must not move other controls or resize its dialog; reserve its space from the start
metadata:
  type: feedback
---

When a form or dialog gains content after an async step, nothing else may move and the container keeps its size.
Hold the space from the moment it opens: render the row with `visibility: hidden`, which keeps its box and takes it
out of the tab order and the accessibility tree. The reserved row is blank until it fills, so put it where a blank
reads as spacing, such as last, above the buttons. The step's own error goes on that reserved row's label line,
kept to a fragment that fits, not in a callout that grows the dialog. A busy indicator goes inside an existing
control (a spinner at the end of the input), not in a new line.

**Why:** a custom-game dialog in the scheduler project revealed a BGG link field once a pasted link's name came
back, and the dialog grew while the user was looking at it. The user's words on 2026-11-14: "come up with a design
where position of the other components and dialog size do not change after name is fetched". Offered three
layouts, they chose the slot reserved above the buttons over one under the name field, which would have left a gap
between two fields, and over showing the link field at all times. Reading that one dialog as a rule for every form
and dialog is the scheduler session's interpretation, which the user approved saving that day. It is the same
complaint as a button resizing on press, one level up.

The same holds across a mode switch and for a transient status. On 2026-11-20 the trips page's Edit and Add icons sat after a name that edit mode turns into a field of another width, so they moved at every switch, and a "Saved" note pushed them again; the user asked for placements where nothing jumps and chose the icons pinned at the heading's top right, by the calendar, with the save shown as a border flash.

**How to apply:** anchor a mode toggle where no field's changing width reaches it, and give a transient status no layout of its own. Before revealing anything after a fetch, ask what moves when it appears; if anything does, reserve
the slot. A form field hidden this way is still submitted and still validated, so until it shows keep it empty
and leave `required` off it; the learning `react-form-submit-paste-and-hidden-fields.md` has the measurements.
The same rule for buttons is in [[feedback_no_underline_links]], and for help text and a dialog that has to
resize in [[feedback_help_text_keeps_its_height]]. The no-help-text rule in [[feedback_minimal_ui_chrome]] means
the reserved slot stays blank, not filled with a hint.
