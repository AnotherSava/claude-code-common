---
name: Branch features that only a reporter can validate
description: A feature whose assumptions are only verifiable in an issue reporter's environment goes on its own branch for them to test; unrelated bugs found while investigating ship to main separately
type: feedback
---
When a feature request comes from an issue reporter whose environment can't be reproduced locally, split the work in two: unrelated bugs found while investigating go to `main` as their own commit, and the feature itself goes on a separate branch with a plan doc, so the reporter can test a build in their real setup before anything merges.

**Why:** the feature's core assumptions are only verifiable in the reporter's environment — merging to main first ships unvalidated behaviour, and mixing incidental bug fixes into the same branch makes the feature diff unreviewable. Splitting also lets the bug fixes ship regardless of how the feature test turns out. The prompting case: a Uplay-emulator support request for achievement-overlay, where the whole design rested on whether the emulator keeps its inline achievement text after an unlock — something only the reporter could observe. Investigating it turned up four unrelated live bugs in the existing Steam path, which had no reason to wait on that answer.

**How to apply:**
- Finish and hand off the main-branch fixes first, then branch. Committing is still the user's call — don't fold the fixes into the feature branch just to avoid asking.
- Keep the feature branch's diff purely the feature.
- Hedge cheaply against unverified format assumptions before shipping the test build, so a failed test means "the design is wrong" rather than "it tripped on something we could have guarded".
- Prefer a reporter's test over a hand-made synthetic fixture for the load-bearing unknown: a fixture built from our own belief about the format can only confirm that belief. See [[feedback_assumptions_vs_facts]].
