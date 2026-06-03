---
name: Prefer loud errors to silent fallback
description: Surface parse/validation failures in UI plus log file; never silently degrade to a safe mode
type: feedback
---

Prefer explicit error messages over silent fallback/degradation in user-facing tooling.

**Why:** User explicitly rejected a proposal to "degrade gracefully to hooks-only mode" when a log parser hit an unknown format — said "I'd rather see an explicit error message than silently ignoring." Silent failures are debugging nightmares.

**How to apply:** When a failure mode is possible in runtime code, surface it in at least two places — typically an in-UI error row AND a log file line. Never just hide it and continue in reduced mode.

**Exception for self-healing races:** transient conditions that resolve on their own (e.g. `ENOENT` while waiting for a file another process is about to create) can be log-only if surfacing them in UI would be repeat noise. The test: "will the next event fix this automatically?" If yes, log-only; if no, loud.

**Surface status on the view the user is actually on.** A progress/error indicator confined to one tab/panel is, for a user sitting on a different tab, the same as no notification. When an operation can get *stuck* (e.g. a retrying background fetch that may never recover), make its state visible on the currently-active surface — even if another view also shows it. And prefer a truthful "…retrying" state (with the underlying error on hover) over a timeout that fabricates a terminal result: timing out into an empty/"none" answer hides an ongoing problem and reads as wrong-but-final. (Distinct from the self-healing exception above, which is about *quick* transients that can log-only.)
