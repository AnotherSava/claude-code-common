---
name: feedback_microcopy_user_facing_state
description: UI microcopy should name the state the user sees, not the internal/API condition behind it (e.g. "No usage yet", not "No active window" mirroring resets_at:null)
metadata:
  type: feedback
---

UI microcopy (tooltips, labels, status text) should describe the **state the user sees**, not the internal/API condition that produces it.

**Why:** User flagged a usage-bar tooltip that read "No active window" — copy that mirrored the API's `resets_at: null` — as unclear ("what window? the app window?"). It reads like a bug. Reworded to "No usage yet".

**How to apply:** When a value has an internal cause and a user-facing meaning, write the user-facing meaning. Ask "what does this mean to the person reading it?" not "what condition triggered it?" Distinct from [[feedback_sentence_case_ui]] (casing) and [[feedback_about_what_not_how]] (declarative vs. instructional) — this one is about internal jargon vs. plain state.
