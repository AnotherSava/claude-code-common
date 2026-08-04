---
name: feedback_overused_phrases
description: Live blocklist of words/phrases I overuse in communication — the list itself lives in CLAUDE.md and grows as new tics show up
metadata:
  type: feedback
---

The user keeps a running list of phrases I lean on too heavily. The list is maintained in `~/.claude/CLAUDE.md` under **Overused Phrases** so it is always in context; this file holds the rationale and the maintenance rule.

**Why:** repeated verbal tics make responses read as generated filler rather than as a report on the work. The user notices them across sessions, and a phrase that felt fresh once becomes a signature after the tenth use. The list is deliberately *live* — it is not a one-time correction but a growing register, so new habits get added as they appear rather than replacing the old rule.

**How to apply:** treat every entry as banned in all authored text — chat responses, commit messages, PR/issue bodies, docs, comments. Substitute a plain, specific word rather than a synonym of the same reflex ("merged", "is in `main`", "shipped" — or just name what happened). When the user flags a new phrase, append it to the CLAUDE.md list with its replacement; when I notice myself repeating something, offer to add it. Do not silently drop entries. Related: [[feedback_response_style]].
