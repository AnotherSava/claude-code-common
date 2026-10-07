---
name: feedback_ralphex_deprecated
description: Ralphex is deprecated as of 2026-10-06 — do not name it in anything newly written, and ask before reaching for the plan-ralphex skill
metadata:
  type: feedback
---

Ralphex is deprecated. Said on 2026-10-06, when a `.gitignore` comment reading `# Ralphex` was found
heading four rules it no longer explained: *"ralphex is deprecated now, don't refer it."*

**Why:** the name had stopped describing what sat under it, and a heading naming a dead tool reads as
licence to delete the rules beneath it — in that repo, `coverage/` and the plan-document negations,
whose removal would have un-ignored build output and started tracking draft plans.

**How to apply:**
- Do not name it in anything newly written — a comment, a doc, a commit message, a config heading.
  Describe what the thing actually is instead.
- The global skill `plan-ralphex` is named after it, and whether that goes too has not been said.
  Ask before invoking it rather than assuming either way.
- This applies **forward only.** Existing references are not a sweep list and not an offer to make
  one — see [[feedback_style_rule_no_history_sweep]].
