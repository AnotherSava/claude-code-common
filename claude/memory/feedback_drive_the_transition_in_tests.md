---
name: feedback_drive_the_transition_in_tests
description: a test that constructs the object at the state under test never runs the transition that fills the field being read, so it exercises the constructor default — often the one value that hides the bug
metadata:
  type: feedback
---

When testing a function that reads a field some *earlier* transition writes, drive that earlier transition. Constructing the object directly at the later state leaves the field at its `Default`, and the default is very often the one value that cannot expose the bug.

**Why:** 2026-09-30. `revert_cancelled_turn` restores `status_before_working`, which `apply_set` captures on every non-Working→Working entry. A redefinition made one status a positive claim that must never be restored blindly, and the guard was missing. The test called `apply_set(Working)` on a fresh state, so no prior transition had ever run and the field still held its constructor default — which happened to be the safe value, so the test passed. The real path (clear the session, type, press Esc) captures the forbidden value and the revert wrote it straight back. Test green, bug shipped; an adversarial review reading the code, not running it, was what caught it.

**How to apply:** for each field the function under test *reads*, ask what writes it and whether the test ever executes that writer. If the answer is "the constructor", the test is measuring the default and nothing else. Build the state the way production builds it — through the same entry points, in the same order — and assert the intermediate value too, so the test says out loud which value it is exercising.

The same shape one level down is [[feedback_fixture_must_exceed_the_cap]]: there the fixture's *value* never reached the branch; here the fixture's *history* never reached it.
