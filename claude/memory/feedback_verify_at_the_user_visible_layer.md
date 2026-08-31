---
name: feedback_verify_at_the_user_visible_layer
description: A successful write in the layer you control is not the outcome — check the surface the user actually sees before reporting a fix as working
metadata:
  type: feedback
---

Before reporting a fix as working, verify at the surface the user looks at — not at the last layer you control.

**Why:** On 2026-08-29 a terminal-tab status glyph was reported fixed on the strength of a `terminal title written` log line, with the write succeeding at every layer I owned — the OSC escape reached the pty, the terminal stored it, and the terminal's own control API showed it under `.title`. The user looked and saw no glyph: a consumer *above* my last checkpoint (a hand-set custom name that outranks the OSC title) was discarding it. Every layer I could see was green and the outcome was still wrong, so "my write succeeded" and "the user sees it" were never the same claim.

**How to apply:** Find the last consumer between your write and the user's eyes and read the value *there*. When you can't — a GUI with no query surface — say "the write succeeds, I can't confirm it renders" rather than "it works", and don't say "go look" as if it were settled. Related: a memo naming a past cause is a claim about *then*; re-derive it from live evidence before restating it as the cause now — I called this same incident "the Claude desktop app" on the strength of an old memo, and it was a shared daemon.

See [[feedback_not_run_is_not_pass]], [[feedback_no_guessed_facts]], [[feedback_live_values_source_of_truth]].
