---
name: ask-before-backcompat
description: Before keeping an unused symbol for "backwards compatibility", ask the user — in most cases backcompat isn't required
type: feedback
---

When refactoring and you're about to keep a function, type, alias, or any other symbol that now has no internal usage purely "for backwards compatibility", **stop and ask the user first**. Don't silently preserve it.

**Why:** Most projects I work on are personal codebases or internal projects — not public libraries with API contracts to maintain. The cost of an unwanted breaking change is low (the user updates one or two call sites), while the cost of accumulated dead code is real (it survives refactor after refactor, clutters search results, and obscures the actual surface area). Defaulting to "keep for backcompat" assumes a constraint that usually doesn't exist.

**How to apply:** During a refactor, when you find yourself reaching for phrases like "keep for backward compat", "preserve for legacy callers", or "in case anything still uses it" — pause. Ask the user a direct question: *"X is no longer used internally. Drop it, or keep it as a public-facing alias?"* The answer is almost always "drop it"; the value is in forcing the user to confirm rather than letting unused code accrete silently.

Related: [[Captured the lesson, drop the code]] — the matching principle for research-stage helpers that have been documented elsewhere.
