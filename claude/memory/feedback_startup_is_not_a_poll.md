---
name: feedback_startup_is_not_a_poll
description: A concern that only exists at startup gets retry-until-answered, not a recurring timer; verify the recurrence before defending it
metadata:
  type: feedback
---

**A concern that only exists at startup gets retry-until-answered, not a recurring timer.**

Real case (tauri-dashboard, 2026-09-02): a feature that put back each live agent's dashboard row after a restart was built as a 30-second reconcile, and the cadence was justified in its own module doc with "the same gap re-opens whenever a row is removed while its session lives". The user asked *"what do we need timer for? isn't it relevant only at the moment dashboard is launched?"* — and 90 days of the app's own decision log showed that gap occurs **zero** times (every removal was either a `/clear`, which recreates the row immediately, or a session that genuinely ended and must not come back). The real problem was a startup *race*: the app and the terminal it queries both start at login in no fixed order, so a single pass at launch routinely asks a program that is not up yet. A bounded retry solves that; a permanent poll only hides it.

**Why:** the recurrence was a hypothesis, written into a doc comment as a fact and never checked. A poll is the shape you reach for when you have not decided whether the thing recurs — it works either way, so it never forces the question. It is also the shape that looks free and is not.

**How to apply:**

- Before adding any recurring timer, **name the recurring event and go count it** in the logs or history. If you cannot find instances, it may not exist, and the honest design is a one-shot.
- The retry's stop condition must be **"the question was answered"**, not "the desired outcome happened". Gating on the outcome degenerates straight back into an infinite poll, because the reasons an item is legitimately skipped do not change with time — the same wrong answer is re-requested forever.
- Bound the retry anyway and log giving up. "Retry until it answers" is an infinite poll on a machine where the answer never comes.
- **A cheap gate is not cheap if it sits downstream of an expensive call.** The one above compared two in-memory lists, but one of them came from a 5s-cached directory read plus a full process enumeration, so every wake paid for both to rediscover the same nothing.
- Say plainly in the doc which of the two it is. "Runs once at startup, retrying while something has yet to answer" is a different contract from "reconciles continuously", and a reader who assumes the second will add work to the tick.

Related: [[feedback-no-permanent-logic-for-one-time]] (permanent *surface* for a one-off — the same instinct on a different axis), [[feedback_sample_level_miss_edge]] (a poll that structurally cannot see what it is asked for), [[feedback_no_guessed_facts]] (do not state an unverified claim as known).
