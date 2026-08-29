---
name: feedback_contribution_vs_mitigation
description: Label an upstream contribution as a contribution, never as a fix for the user's own problem
metadata:
  type: feedback
---

When recommending an action that benefits a third party rather than the user — filing an upstream bug, commenting on someone's PR, contributing a fix — label it as a contribution, not as a fix for the user's problem. Don't list it under "what to do" alongside actual mitigations.

**Why:** on 2026-08-27 I put "comment on agterm PR #461" in a *What to do* section directly after establishing that the PR could not affect the user's setup at all (their hooks were uninstalled). The user caught it: "why did we bother commenting on issue, then?" The facts were right and the comment was worth posting; the framing implied a benefit that didn't exist.

**How to apply:** separate "this fixes your problem" from "this helps the project / the next person." Both are legitimate recommendations — but say which one it is, and say plainly when the answer to "what does this do for me" is *nothing*. Related: [[feedback_no_guessed_facts]], [[feedback_live_values_source_of_truth]].
