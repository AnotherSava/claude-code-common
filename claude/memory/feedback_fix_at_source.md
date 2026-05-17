---
name: Fix bugs at the source, not in callers
description: When a bug lives in code I can modify, fix it where it originates rather than working around it in the caller — root-cause fixes prevent the bug from biting other code paths and avoid accumulating workaround cruft
type: feedback
---
If I find a bug whose source is in code I can modify (this project's own code, or a workspace I own), fix it where it originates rather than working around it in the caller.

**Why:** A workaround in one place leaves the bug live for every other caller and accumulates as cruft. Root-cause fixes prevent silent breakage elsewhere and keep the codebase honest. Personal projects in particular have no backwards-compatibility constraint, so the "small fix vs. big rewrite" calculus tilts further toward the fix.

**How to apply:**
- Before adding a workaround comment ("function X has a bug, so we…"), ask: can I fix X instead?
- Before drafting a wrapper / shim / parallel implementation, check whether the underlying primitive can take the fix.
- If the fix is large or risky, propose both paths (workaround now, root-cause fix as follow-up issue) and let the user choose.
- If the bug is in a third-party library, workarounds are fine — note the upstream issue if known.
- Strong trigger for user pushback: any phrasing like "since it is located in this very project" or "in code we own" means I should have already fixed the source.
