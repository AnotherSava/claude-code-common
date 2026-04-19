---
name: Fix failing skills instead of working around them
description: When a skill fails (shell expansion, hook error, etc.), fix the skill itself rather than bypassing it with a manual workaround
type: feedback
---

When a skill or tool fails (e.g. shell expansion error, hook failure), fix the root cause in the skill definition rather than working around it manually.

**Why:** A workaround means the skill stays broken and will fail again in the next session. Fixing it once saves repeated friction.

**How to apply:** If a `/commit`, `/pr-create`, or any other skill errors out, read the SKILL.md, diagnose the failure, fix it, then re-run the skill. Only fall back to manual execution if the fix is impossible within the current session.
