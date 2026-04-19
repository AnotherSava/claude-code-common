---
name: Follow skill instructions exactly
description: Never abbreviate, summarize, or skip steps defined in skill SKILL.md files — even when the output feels verbose or the work feels redundant
type: feedback
---

Always follow skill instructions literally. Do not optimize for brevity by skipping or abbreviating steps.

**Why:** Two observed failure modes:
1. Abbreviating output — when a skill says "list every commit," I shortened to a summary. The user wants every item listed individually.
2. Skipping steps because prior conversation work "already covered it" — the /commit skill has a dead code audit step. I skipped it because I'd done extensive dead code auditing earlier in the session. But the skill step exists precisely to catch anything missed, and "I already did this" is not a valid reason to skip a numbered step.

**How to apply:** When executing any skill, treat every numbered step as a mandatory checklist item. Execute each one in order regardless of what happened earlier in the conversation. If a step produces no findings (e.g., dead code audit finds nothing), say so explicitly — but still run the check. If the output feels too long or the work feels redundant, that's the skill author's decision to make — not mine.
