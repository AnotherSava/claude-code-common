---
name: feedback_verify_at_the_user_visible_layer
description: A successful write in the layer you control is not the outcome — check the surface the user actually sees before reporting a fix as working
metadata:
  type: feedback
---

Before reporting a fix as working, verify at the surface the user looks at — not at the last layer you control.

**Why:** On 2026-08-29 a terminal-tab status glyph was reported fixed on the strength of a `terminal title written` log line, with the write succeeding at every layer I owned — the OSC escape reached the pty, the terminal stored it, and the terminal's own control API showed it under `.title`. The user looked and saw no glyph: a consumer *above* my last checkpoint (a hand-set custom name that outranks the OSC title) was discarding it. Every layer I could see was green and the outcome was still wrong, so "my write succeeded" and "the user sees it" were never the same claim.

**Run the real system when it is reachable, rather than a stand-in you built.** A synthetic fixture agrees with your own model of the code by construction, so it confirms what you already believed and nothing else. On 2026-09-16 a status script's state-file path was checked by calling one function on a hand-built dict; it passed. Asked "why not use real environment?", the real run printed the same warning 22 times — once per repo, for a fact about one file — which no isolated call could have shown. Keep a synthetic case only for a state the real environment can no longer produce (there, a file written by the previous version of the script), and say that is what it is.

**Make a transient state last long enough to see before asking anyone to watch it.** A pending state that ends before the first paint cannot be observed, and "it showed the result right away" fits a UI that blocked just as well as one that did not. On 2026-09-28 a Settings card was predicted to say "checking…" while it counted in the background; a warm file-system cache finished before the window painted, so only the result ever showed. A temporary 5-second delay in the background task, marked for removal and taken out after, made the pending line visible and let the user confirm the window stayed responsive, which was the claim under test. Build the delay into the check build up front rather than predicting the state will be visible.

**How to apply:** Find the last consumer between your write and the user's eyes and read the value *there*. When you can't — a GUI with no query surface — say "the write succeeds, I can't confirm it renders" rather than "it works", and don't say "go look" as if it were settled. Related: a memo naming a past cause is a claim about *then*; re-derive it from live evidence before restating it as the cause now — I called this same incident "the Claude desktop app" on the strength of an old memo, and it was a shared daemon.

See [[feedback_not_run_is_not_pass]], [[feedback_no_guessed_facts]], [[feedback_live_values_source_of_truth]].
