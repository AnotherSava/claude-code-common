---
name: feedback_break_the_subject_to_prove_the_test
description: A test you just wrote is unproven until you break what it measures and see which cases fail — a case whose expected value matches the subject's failure path cannot discriminate and looks identical to one that can
metadata:
  type: feedback
---

A test you just wrote is unproven until you break the thing it measures and watch which cases fail. The ones that stay green are not testing what they claim, and no other instrument reports it.

Measured 2026-10-09 while consolidating two copies of a repo-root resolver, plus an inline git top-level lookup, into one shared function. Seven cases, all green. Breaking the resolver's anchor match — one token into the path it tests — failed only two. Four of the remaining five were pinning fallbacks and were correctly unaffected; the fifth, `nearest-wins`, probed from the project root, where the function's `$PWD` fallback returns that same directory, so a correct answer and a broken one were the same string. Re-pointing it one level down made it catch the break, taking the count to three of seven. The same collision had already produced a *false failure*: an isolation case asserting "must not resolve here", run at the root, read the `$PWD` fallback as a wrong match and reported a defect in a correct function.

**Why:** a case whose expected value coincides with what the subject returns on its failure path cannot discriminate, and it is indistinguishable from one that can — green, named for the property it claims to pin, sitting in a passing suite. The collision runs both ways, so the same positioning that hides a real defect also invents one that is not there. Fixture size has this shape too and carries its own memory; this is position, and the instrument for both is the deliberate break.

**How to apply:** once a suite is green, break the subject at its narrowest point — one condition, one constant — and re-run. Count the failures and name them. Where a case you expected to catch it stays green, move the fixture until the correct and the incorrect answer differ, rather than deleting the case; a case pinning a fallback is allowed to stay green, so say which of the two each one is. Restore with the inverse edit and confirm green again, so the break cannot ship. Sibling of [[feedback_fixture_must_exceed_the_cap]], the size version, and [[feedback_not_run_is_not_pass]], where a check cannot tell success from never-ran.
