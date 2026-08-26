---
name: No defensive fallbacks
description: Never substitute a plausible value for one you don't have — not for invalid input, not for a gap in the logic
type: feedback
---

Do not add defensive fallbacks (e.g. `?? "?"`, `?? 0`, `?? "unknown"`) that silently produce plausible-looking output from invalid data.

**Nor from a gap in the logic.** Where the code cannot determine a value, it must not pick one that looks right and carry on: keep the wider, honest answer, or fail loudly. A guess nothing can currently observe still counts — the moment some later change reads that field, the guess is served back as fact. Real case: a card tracker pinned a name to one of two indistinguishable slots because no code read slot order; when it later started reading the server's own slot index, that coin flip became a confidently wrong answer.

**Why:** Defensive fallbacks hide bugs in upstream logic. A visible `null`, a wider candidate set, or a runtime error is easier to catch and debug than output that looks correct but isn't.

**How to apply:** Trust that inputs are correct. Only add validation at true system boundaries (user input, external APIs). For internal data flowing between modules, let invalid values propagate naturally so they fail visibly. When a deduction is under-determined, prefer the honest superset over a pick, and prefer throwing over inventing — then see [[feedback_loud_errors]] for surfacing the failure once it happens.
