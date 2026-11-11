---
name: Never rewrite a file region by blind marker-to-marker splice
description: When replacing a block of a file, read what lies between the anchors first — index/marker splices silently delete unrelated working code between them, surfacing later as a user-visible bug with no error at edit time
type: feedback
---
When rewriting a region of a file, do not splice between two textual markers (`s[:start] + new + s[end:]`, or line-index slicing) without first reading everything between them. Prefer a targeted `Edit` on the exact block being replaced.

**Why:** A marker splice is an *invisible deletion*. Nothing errors, tests that don't cover the deleted lines stay green, and the loss only surfaces later as broken behaviour — so the eventual debugging starts from the wrong hypothesis, hunting the feature being worked on rather than the collateral. This happened twice in one session: rewriting a CSS block between a comment marker and the next section deleted the unrelated rules that happened to sit between the anchors, and the user hit the resulting layout bug several turns later.

**How to apply:**
- Default to `Edit` with the full old block as `old_string`. It fails loudly on a mismatch, which is the desired behaviour.
- If a region rewrite is genuinely necessary, read the span between the anchors first and confirm the end marker is where you think it is.
- After any splice, diff or re-read the touched region rather than trusting the write.
- In a scripted edit, assert the old text occurs exactly once (`assert s.count(old) == 1`) before replacing. Taking the block as `s[s.index(a):s.index(b)]` fails the other way when `b` also occurs before `a`: the slice is empty, and `s.replace('', new)` inserts `new` between every character of the file. On 2026-11-10 that scrambled a whole server-actions file, which a `git checkout` restored only because it had no other uncommitted changes.
- Suspect this class of bug when something that previously worked breaks near, but not in, the code just edited — see [[feedback_post_iteration_cleanup]].
