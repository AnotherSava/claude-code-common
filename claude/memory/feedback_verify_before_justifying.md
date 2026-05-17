---
name: Verify before justifying legacy behavior
description: When explaining why old code/docs/steps exist (especially when arguing against removing them), check the source instead of speculating defensively
type: feedback
---

When tempted to explain why a piece of legacy code, documentation, or workflow step exists — especially when the explanation defends keeping it — verify the justification has a real basis (read the source, check the spec) before stating it.

**Why**: In a track-achievements session on 2026-05-04, I claimed an outer `steam_appid.txt` step "predates achievement-overlay and is for GBE-side reasons (some games look for it at the exe location)". The user replied "is it?" — I checked GBE's `dll/settings_parser.cpp:560-643` and the claim was unfounded. GBE's lookup priority puts `steam_settings/steam_appid.txt` (#2) above the exe dir (#4), so the outer copy was redundant once GBE was loaded. The defensive guess almost preserved cruft.

**How to apply**:
- When writing "this exists because some/many/legacy X do Y" or "this is defensive against Z" — either cite the source/spec inline, or rephrase as "I'm not sure why this is here — let me check" before defending.
- The pattern is most dangerous in two situations: (1) deciding whether to remove a workaround, and (2) explaining historical decisions in code comments or docs.
- A short factual "I don't know — checking" is always better than a confident speculative justification.
