---
name: Eliminate the bug class, don't patch paths
description: A bug recurring after a targeted patch signals the fix was at the wrong altitude; remove the structural property that enables the whole class
type: feedback
---

A bug that **recurs after a targeted patch** is a signal the fix was at the wrong altitude.

**Why:** When a symptom comes back through a new trigger path, the per-path patch only closed one hole; the next untested path leaks through the same structural weakness. In this project, "Summary stuck on Loading labels…" had already been patched once (one trigger path), then recurred via another — because the real cause was a *push-only, broadcast-once* delivery that left the consumer strandable. Patching the new path would have just deferred the next recurrence.

**How to apply:** On recurrence, stop patching paths and find the structural property that makes the whole class possible — a once-flag, push-only delivery to a consumer that can lose its copy, an implicit ordering dependency, a sentinel field. Eliminate it: e.g. switch push→pull so the consumer asks on demand and can't be left stranded; resolve derived state where the source of truth lives instead of shipping it around. Prefer dissolving the class when there's a single chokepoint to hook the robust mechanism into. Related: [[feedback_fix_at_source]] (fix at the origin, not the caller) and the "broadcast once" / "pull must wait for readiness" notes in the chrome-extension learnings.

**The same instinct applies pre-emptively, not just on recurrence.** Diagnosing a compact-header bug (an "unstick once the bar grows past 3× the smallest height ever seen" baseline that a permanently-tall bar poisons on its very first measurement — no smaller reading ever recorded to compare against), the first fix proposed keeping that 3×-baseline check and adding a second, absolute-pixel-ceiling check *on top* for the case it missed. User: "let's do fix in all the cases, not on top of x3" — rejected the two-mechanism patch for a single fixed-ceiling replacement, since it alone already covered both the original case (transient growth) and the edge case (tall from the start), with no need to carry the old, now-partially-redundant logic forward. Before adding a new check to cover an old one's blind spot, ask whether the new check (redesigned) already covers everything the old one did — if so, replace, don't stack.
