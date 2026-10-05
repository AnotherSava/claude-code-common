---
name: feedback_reject_what_was_proposed
description: Before rejecting a proposal on contract or principle, restate it in that contract's own terms and check you are rejecting what was actually proposed — a version floor and a currency check look alike and only one is forbidden
metadata:
  type: feedback
---

**Before rejecting a proposal on contract or principle, restate it in that contract's own terms and
check you are rejecting what was actually proposed.**

**Why:** seen 2026-10-04. Asked "should we do it as a next convention version?", I answered a
proposal nobody had made — "is this repo on the latest tauri" — and rejected it with three numbered
reasons, a cited precedent from `conventions/not-versioned.md`, and a substitute to do instead (write
a learning). The reply was one line: *"i thought of a rule about >= 2.12.1, not that we are on
latest"*. A **floor** on the version where a defect was fixed and a **currency** check against
whatever upstream published this morning look alike, read alike, and are both "a rule about a
dependency version" — but only the second asserts something that expires, which is what versions are
forbidden to do. Applied to the real proposal, the authoring contract's own test settled it in one
line, and it was already written down: "a repo already conforming to the previous version must now do
something", plus "a rule no repo currently violates still qualifies, because a rule runs only where
the adopted number is at or above the version introducing it". The answer flipped from no to yes, and
the subject ended up better than either of us first named — a floor on the crate that actually
carried the defect rather than on its parent.

**How to apply:** the tell is a rejection that arrives with a general principle and a consolation
prize. Both were mine here: I quoted a precedent about Node pins, and I invoked
[[feedback_no_permanent_logic_for_one_time]] — a real rule the domain contract had already overruled
in writing, for exactly this case. So before drafting the argument, say back in one sentence what
invariant you are about to refuse, then find the governing test and run it against that sentence,
rather than reasoning from the principle you happen to remember. A proposal naming a specific number
is almost always a floor; "latest", "current" and "up to date" are the currency form, and a floor on
a fixed defect never moves. Where the two readings genuinely both fit, ask which one they meant — one
question costs a line and the wrong rejection costs the whole argument.

Distinct from [[feedback_honor_concrete_example]], which is about substituting your own abstraction
for a concrete example while implementing; this is the mirror, substituting a weaker reading of a
*proposal* and then arguing against the substitute. See also [[feedback_check_the_limit_is_real]]'s
second shape, a general rule reported as binding where its premise does not hold.
