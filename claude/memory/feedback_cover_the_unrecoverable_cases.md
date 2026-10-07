---
name: feedback_cover_the_unrecoverable_cases
description: A retention or undo mechanism is judged by which cases it reaches, ranked by the cost of redoing each — placed at one caller of a shared step it covers only that caller
metadata:
  type: feedback
---

When adding anything whose job is to make work recoverable — a kept copy, a backup, an undo record,
a snapshot — do not judge it by whether it runs. Judge it by **which cases it reaches**, ranked by
what redoing each one costs. The cases at the top of that list are the whole reason it exists.

Measured 2026-10-06 in bga-assistant. A convention required each documentation screenshot's
pre-frame capture to be committed, so the framing could change without re-taking the picture. The
copy went into `shoot.py`, the headless capture script, because that was the file in hand. It
covered the 7 frames a script rebuilds from a committed fixture — where a re-shoot costs one
command — and missed all 12 hand-taken ones, two of them marked `never` re-capturable because they
need a live game offering a state that cannot be staged. The protection sat where loss was
cheapest. The convention had named the right file; one helper called from the frame step covered
both routes.

**Why:** a mechanism that runs, writes real files and passes every check reads as finished, and the
gap is invisible from the call site, because the artifacts it does produce are the ones you can see.
Nothing reports that the irreplaceable case took the other route.

**How to apply:**
- Enumerate the entry points into the step being protected before choosing where the hook goes, and
  put it at the shared step rather than at whichever caller you were already editing.
- Sort the cases by the cost of redoing them and confirm the hook reaches the worst one. The
  question is which case this is for.
- Where a spec, convention or migration names a file to change, changing a different file that
  reaches the same effect covers a subset. Put it where you were told, or say why not.

Related: [[feedback_fix_at_source]] is the same geometry for a bug — fix the primitive, not the
caller. [[feedback_fix_the_class_not_the_instance]] is the same for a guard over an enumerated set.
