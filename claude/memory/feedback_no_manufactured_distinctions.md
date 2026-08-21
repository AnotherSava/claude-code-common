---
name: feedback_no_manufactured_distinctions
description: Don't invent states, controls or feed entries the underlying source doesn't require — collapse derived distinctions and fold optional actions into the routine one
metadata:
  type: feedback
---

Don't manufacture distinctions or manual steps the source doesn't require. Three corrections in one session
(2026-08-20, the scheduler project), all the same shape:

- *"do not separate open and limited events"* — `limited` was a bucket the app derived from a seat count via a
  configurable threshold; no source published such a state. Collapsed into `open`, with `seatsAvailable`
  carrying how nearly gone the seats are. Removing it also removed a changelog entry every time a count crossed
  the threshold.
- *"'Pull my sign-ups' shouldn't be a separate button, it should always be a part of the sync"* — an optional
  manual action folded into the routine refresh that was already running.
- *"do not add items in the initial fetch to 'changes' page"* — a feed whose every row reads "new" says nothing.

**Why:** recorded as the pattern the three corrections share, not as a rationale the user gave — none of them
came with one. Do not attribute motives beyond this.

**How to apply:** before adding a state to an enum, an option to a filter, a colour to a badge, or a button to a
page, check whether the underlying source actually draws that line or whether the app is inventing it. If
invented, default to not having it and let the underlying number or the existing control speak. Prefer folding
an action into an existing routine one over adding a control someone has to remember to press. When a derived
distinction feeds a changelog or notification, weigh that too — an invented state boundary generates events
every time something crosses it. Related: [[feedback_minimal_ui_chrome]].
