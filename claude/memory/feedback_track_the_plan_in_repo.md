---
name: feedback_track_the_plan_in_repo
description: For work spanning more than one session, keep a living status tracker in the repo rather than in conversation
metadata:
  type: feedback
---

For work that spans more than one session, keep a living tracker in the repo. Asked for it partway through a
long build (2026-08-27): *"what about a plan - so that you could trace it, add items that arise and mark
already completed ones"* — after several turns of reporting status in prose.

Sections that earned their place, in `docs/plan.md`:

- **Done**, grouped by area and dated, distinguishing `[x]` verified from `[~]` built-but-unverified. That
  distinction is the point of the file, not decoration — it is what stops "it compiles" being read as "it
  works".
- **Next**, split into what can just be done and what is **blocked on the user**.
- **Known defects, unfixed** — real defects stated as such rather than quietly dropped.
- **Unverified assumptions** — claims the repo makes that nobody has watched hold.
- **Decisions on hold**, with who parked them and when.

**Why:** prose in chat does not survive a context reset, and the user cannot read it without asking. Writing it
down also surfaces what prose let me skate past — filling in the sections exposed two real gaps that several
status summaries had not.

**How to apply:** create it once the work outgrows a single reply, keep it current as work happens rather than
at the end, and keep state in exactly **one** file. Where a runbook already tracks its own steps, have it point
at the tracker instead of repeating them; two files claiming what is done is how a runbook ends up asserting a
step is complete when it is not.

Distinct from memos (`.claude/memos.md`, the **Memos** section of the global CLAUDE.md), which park *ideas
that are not part of the current work*. This tracks the work itself.
