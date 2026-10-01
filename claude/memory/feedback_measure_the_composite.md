---
name: feedback_measure_the_composite
description: A measured unit times an assumed count is not a measurement — measure the composite from outside, since the real number hides the invented factor
metadata:
  type: feedback
---

A measured unit multiplied by an assumed count is not a measurement. Measure the whole thing from the outside instead, where the composition is observed rather than reasoned.

Measured 2026-09-30. One Claude Code hook guard was timed honestly at ~22 ms. The count of eight came from reading `settings.json` and seeing eight entries. The product — "every Bash call spawns 8 guards, ~200 ms per call" — was reported to the user twice as a measurement, and used as an argument against adding another hook. The user asked whether that was really true. Pairing each `tool_use` with its `tool_result` in the session transcript put the fastest Bash round trips at **40 ms including hooks**, so the claimed overhead alone exceeded the whole observed call by more than four times. The eight entries were not duplicates either: each carried a distinct `if` pattern, and a non-matching `if` costs zero process startup, so a typical call starts none of them.

**Why:** the measured factor makes the invented one invisible. "22 ms each" is true, carries the authority of a stopwatch, and lends it to a multiplication nobody checked. Two further errors followed from the same reading — a defect reported in the user's settings that did not exist, and a model of serial execution that was never tested.

**How to apply:** find an instrument that sees the composite. For anything inside the agent loop the transcript is that instrument: every row is timestamped, so the gap from a tool call to its result bounds everything the harness did in between, hooks included. When no such instrument exists, report the unit and name the count as an assumption rather than folding them together. The worked case, including which tools a hook chain actually starts, is in the `hooks` skill's findings log. See [[feedback_no_guessed_facts]] and [[feedback_state_the_enforcement_reach]].
