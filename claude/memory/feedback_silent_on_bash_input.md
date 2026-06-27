---
name: feedback-silent-on-bash-input
description: When the user runs a `!` command themselves (bash-input / local-command), stay silent — don't analyze or comment unless they ask
metadata:
  type: feedback
---

When the user runs a command themselves via the `!` prefix (it arrives as a `<bash-input>`/local-command result, carrying the caveat "DO NOT respond unless explicitly asked"), treat it as a no-op: return control immediately, no analysis, no acknowledgment, not even "looks good." It's *their* action, not a request to me.

**Why:** After the `! memo` width work I kept replying to each `! memo` the user ran — "Clean now…", "No response needed — looks good." The user: *"why do you go into analysis mode after the script run? I'd rather you return control to user right away."* Those replies cost a turn and their time to produce pure noise, and they ignore the explicit caveat on those messages.

**How to apply:** A bare `!`-command result → say nothing, yield the turn. Only respond when the user actually asks a question, or when the output is something they're clearly surfacing *to me* for help (an error, an unexpected result with an implicit "what's this?"). When unsure, default to silence over a filler reply. Related: this is the opposite failure from over-explaining — see [[feedback-no-permanent-logic-for-one-time]] only loosely; the core is *don't manufacture a response where none is wanted.*
