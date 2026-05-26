---
name: honor-concrete-example
description: When the user gives a concrete example of the behavior they want, implement that exact rule first — don't silently substitute a more general one
metadata:
  type: feedback
---

When the user gives a concrete example of behavior they want, that example IS the spec. Implement it literally first. If you think a more general or "more robust" rule would be better, ASK before substituting — don't silently re-scope.

**Why:** Asked to add a click-to-expand collapse feature to the history view, the user pointed at a specific structural pattern: text between `---` separator lines. I instead implemented "collapse any entry longer than 10 lines" because it felt more general. The user pushed back: *"why did you set this rule instead of parsing specific entries (between '---')?"* I had to admit I'd substituted my own design choice for their concrete signal. Reimplementing to match the actual request took five minutes; the deviation eroded trust and wasted a turn.

This is distinct from [[no-bluffing-external-uis]] — that memory is about *making up facts*. This one is about *substituting my abstractions for what the user actually showed me*.

**How to apply:**
- When the user shows a concrete example or names a specific marker/pattern/threshold, treat that as the literal spec. Implement exactly that first.
- If a more general rule would genuinely be better (catches more cases, fewer edge cases), ASK before generalizing: *"You pointed at X — should the rule also handle Y/Z, or just X?"*
- "More robust", "more general", "catches edge cases" are my judgment, not the user's. They are speculation until confirmed.
- Don't dress up substitutions as "what they probably meant." If the literal request reveals itself to be too narrow during implementation, raise it as a question — not a silent re-scoping.
- Generalization-by-default (e.g. extracting a regex when they named one literal string) is the same mistake in smaller form. Match what they showed.
