---
name: discuss-before-rewriting-deliberate-behavior
description: Don't rewrite considered/deliberate behavior off a single offhand comment — propose, preview, confirm first
metadata:
  type: feedback
---

When the user muses about or critiques a behavior in passing ("I'd like messages like this in history too"), do NOT immediately rewrite the design and deploy — existing behavior is often deliberate. Propose the change, show a preview/tradeoffs, and confirm before implementing, especially when it changes stored data or established logic.

**Why:** I twice rewrote the tauri-dashboard dialog-history merge (last-assistant-per-turn → append-all) off single comments; the user pushed back — "appending all the messages was not the goal… previous behaviour was well thought-through, you can't change it based on my single comment" — and we reverted to the original.

**How to apply:** Treat a passing remark as the start of a design discussion, not a ship order. Generating a quick preview of the proposed change (e.g. an HTML mock) to compare against the current behavior is a good way to drive that discussion. Related: [[feedback_honor_concrete_example]].
