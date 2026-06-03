---
name: About dialogs describe WHAT, not HOW
description: About content stays declarative — what the app is and what it provides; usage instructions belong in docs, not the About dialog
type: feedback
---

About dialogs describe **what** the app is and what it does — they're not the place for usage instructions or "double-click to do X" style affordance documentation.

**Why:** User correction during the AboutApp content pass — I wrote "Double-click any row to review its recent prompts and replies in a scrollable history." The user pushed back: *"About window is not about instructions or 'how', it's about 'what'."* Reframed to "Each session also keeps a conversation history" — same fact, declarative form, no action verb directed at the user.

**How to apply:** When writing About copy, list capabilities as nouns/state, not as user actions:

- ✅ "Each session keeps a conversation history."
- ✅ "Tracks state, task, model context usage, and a conversation history."
- ❌ "Double-click a row to open its history."
- ❌ "Click X to do Y."

Usage walkthroughs belong on the documentation site (GitHub Pages, README, in-product Help → docs link). About copy should read as if the app were describing itself in third person.
