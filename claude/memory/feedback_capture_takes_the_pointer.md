---
name: feedback_capture_takes_the_pointer
description: A capture script that needs the pointer out of the way moves it itself and puts it back, rather than refusing; the run is confirmed right before it starts
metadata:
  type: feedback
---

A capture script that needs the pointer clear of what it photographs (a hover tooltip, a highlighted row) moves the pointer itself and puts it back afterwards, rather than refusing and asking the user to move it. The run is confirmed with the user immediately before it starts, as **Taking Over the Machine** in the global CLAUDE.md requires — the confirmation is what makes moving the pointer acceptable, not a reason to avoid it.

**Why:** a refusal turns a one-word confirmation into a manual round trip. On 2026-10-13 the work-intensity-macos capture refused because the pointer sat over the chart, and the user asked for the script to park it instead, keeping the confirmation before each run.

**How to apply:** park away from screen corners, which can be Hot Corners (`learnings/macos-app-automation-and-capture.md`), restore the original position in a `finally`, and keep the pointer-inside-window check as a backstop, since the window may open where the park lands.
