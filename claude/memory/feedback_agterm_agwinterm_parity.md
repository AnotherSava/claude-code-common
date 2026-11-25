---
name: feedback_agterm_agwinterm_parity
description: before proposing the dashboard adopt an agterm capability, check agwinterm supports the same; where it does not, point agwinterm at the same form
metadata:
  type: feedback
---

Before proposing that tauri-dashboard adopt an agterm capability, check whether agwinterm supports the same. Where it doesn't, the proposal also asks agwinterm to build it in the same form, so one dashboard setting means the same thing on both terminals.

**Why:** on 2026-11-24 the user made offering agterm's `#rrggbb` session tints to the dashboard conditional on agwinterm supporting the same. agwinterm had no session tints at all. The user then asked that agwinterm's tints take `#rrggbb` from the start, and memos went to both repos.

**How to apply:** check agwinterm's tree on its newest branch, by whole word, and the dashboard's agwinterm adapter, before writing the proposal. Name the gap in it, and route the matching form to agwinterm's session as a memo. Related: [[user_windows_agents_viewable_on_windows]].

**Exception, chosen 2026-11-24:** agwinterm's session tint takes `#rrggbb` hex but not the five named colours agterm 0.41.0 added (teal, pink, brown, indigo, mint). Its named set stays at red, orange, yellow, green, blue, purple and gray, so don't route those five names to agwinterm as a parity gap.
