---
name: feedback_guard_the_input_not_the_output
description: A check placed after a transformation cannot see what was missing before it; when the failure mode is absence, guard the input
metadata:
  type: feedback
---

A guard that runs **after** a transformation can only see damage the transformation left behind. When the failure you are guarding against is *absence* — a placeholder the template never carried, a field never in the payload, an element never in the list — the output comes out clean and the guard waves it through. Check the input, before the transformation.

**Why:** On 2026-08-26, extending `/github-create` to seed an all-rights-reserved LICENSE, I wrote a guard that scanned the *substituted* licence text for leftover `[year]` / `[fullname]` placeholders. A template missing `[fullname]` entirely leaves nothing to find, so the guard passed a licence naming no copyright holder — into a root commit, the hardest commit in a history to change. Two of five test cases went green for the wrong reason. Moving the same check onto the template, before substitution, caught all of them and subsumed the original check as well.

**How to apply:** When writing a guard, ask what state it can actually observe *at the point it runs*, and which failure mode it faces — presence-of-something-wrong (check the output) or absence-of-something-required (check the input). Then test the guard by deleting it: if the negative cases still pass, it was never doing anything, and a passing test suite is telling you nothing. Related: [[feedback_validate_self_gating_edits]] (a validity check is not a correctness check — JSON stayed valid while the command string inside it broke) and [[feedback_eliminate_bug_class]] (a guard at the wrong altitude closes one hole and leaves the class open).
