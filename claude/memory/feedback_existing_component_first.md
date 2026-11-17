---
name: feedback_existing_component_first
description: Before building a common UI widget, look for an existing component; where only heavy design systems ship it, compose it from the library already in use and show the evidence
metadata:
  type: feedback
---

A widget seen on "every second web site" is not something to hand-roll before checking what exists. Proposing a
custom time field drew "isn't there an existing component that complies with the requirements you listed? it feels
strange to implement something that is used on every second web site" (trips repo, 2026-11-16).

The answer that settled it was a survey, not an assertion: the calendar-style time field ships only inside full
design systems (Fluent UI, Atlassian), each bringing its own provider, theme and styling engine, while the
lightweight libraries (React Aria, Radix, Headless UI, shadcn) ship none. So the field was built from the component
library the app already used, as a combobox fed a list of times, with only a small parser of its own.
Details: `~/.claude/learnings/time-of-day-entry-fields.md`.

**Why:** the user expects common UI to come from a maintained component, and treats custom code for it as a cost to
justify.

**How to apply:** before proposing a hand-built control, name the existing components that come close and what each
costs (dependency weight, a second design system, missing behaviour). Prefer composing from a library already in
the app over adding a second one; say which and why in the proposal. Where the project keeps a register of library
components (trips: `docs/ui-components.md`), add the row.
