---
name: feedback_read_the_control_point
description: What gates an action is a findable artifact — read it before saying nothing enforces something, and anchor a new check on it rather than on the behaviour's symptoms
metadata:
  type: feedback
---

Asked whether something is allowed or prevented, find the thing that actually decides and read it.
Prose describing the intent is a different surface from the mechanism that enforces it, and they
live in different files.

Measured 2026-10-01. Asked whether pushing outside `/commit` had been forbidden, I grepped
`CLAUDE.md` and the conventions, found only "do not push to remote unless explicitly requested", and
answered "No rule forbids it." The gate existed: `autoMode.soft_deny` in `claude/settings.json`
carries a `Push to GitHub` rule covering every form of `git push`, pushes run from a skill included,
and its clearing condition enumerates the skills whose invocation counts as the user asking. The
correction was *"i thought we decided to disable push in auto mode"* — naming the file a prose grep
cannot reach.

**Why:** the enforcement surfaces are separate and only one of them is prose. `CLAUDE.md` states
intent, `settings.json` (`permissions`, `autoMode`) is evaluated per call, a hook refuses at the tool
boundary, a commit gate refuses at the commit. "Nothing enforces this" is a claim about all of them,
so it takes all of them read.

**The same applies one step further, to building a check.** Where a control point already enumerates
who may do a thing, a new check reads that enumeration rather than re-detecting the capability. The
first design for coupling "pushes" to "tells the other machine to pull" scanned each skill for a
`git push` command, and was rejected: *"i expect new skill outside of that list not to be able to
push no matter if it plans or doesn't plan to notify peer"*. Keyed to the symptom, such a check
passes a skill that pushes without authorization and fails one that is authorized and spells the
command differently; keyed to the list, it asserts exactly the obligation the list creates. Rebuilt
that way it immediately caught its own first draft — matching the helper's basename counted a skill
that *documents* the notice as one that sends it, so it had to match the invocation instead.

**How to apply:** before writing "nothing stops this", name the surfaces you read. Before writing a
check that couples a capability to an obligation, find what authorizes the capability and read that
— a grep for the behaviour is a guess about where it enters.

Related: [[feedback_guard_on_version_not_artifact]], the same preference for the authoritative record
over the artifact's shape; [[feedback_state_the_enforcement_reach]], which bounds what a check you
did read entitles you to say.
