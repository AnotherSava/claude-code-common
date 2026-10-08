---
name: feedback_do_the_prerequisite
description: A request naming an outcome implicitly requests the one prerequisite it cannot be honoured without — do it rather than asking which order to work in
metadata:
  type: feedback
---

When a request names an outcome whose prerequisite is unambiguous, do the
prerequisite rather than asking which order to work in. "Ping the other machine
to pull and restart" presupposes a commit and a push, because the outcome is
unreachable without them — so it *is* the explicit request the Git Workflow
rules ask for, not a licence to be inferred around them. Asking instead spends a
round trip approving what the request already said.

**Why:** 2026-10-08, asked to ping the other machine to pull a fix that was
still uncommitted. The honest half was right — there was nothing to pull, and
saying so mattered — but it came with a three-option menu (commit and push then
ping / restart only / hold) instead of the commit. The menu was declined and
`/wrap-up` run next, which commits and pushes: the work the question was asking
permission for.

**How to apply:** Do the implied prerequisite, then say that you did and why it
was implied, so the reader can object to the reading rather than to the result.
The limits are the ones that already apply to any action: ask anyway where the
prerequisite is destructive, irreversible or outward-facing, where more than one
prerequisite would satisfy the request, or where doing it would publish
something — a push to a shared remote is fine as a prerequisite for "tell the
other machine to pull", and is not fine as a prerequisite for something the user
never asked to be visible. Reporting that a thing had to happen first is never
optional; only asking first is.

This narrows [[feedback_keep_your_half]] rather than contradicting it: handing
back the part that needs a human stays right, and an ordering the request has
already fixed is not that part.
