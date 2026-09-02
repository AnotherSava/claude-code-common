---
name: feedback_settled_design_means_build_it
description: When the user settles a design question, build it next — don't record the decision and resume the workflow that was in progress
metadata:
  type: feedback
---

**When the user settles a design question, the next step is building it — not recording it and moving on.**

Twice in one session I treated a closed decision as documentation. After the user chose departure-marking over arrival-marking and asked for the terminal integration to be structured as an adapter, I wrote both decisions into project memory and returned to the in-progress `/commit` — and had to be asked *"wait, what about implementation?"*. Earlier in the same flow I had presented a commit plan whose feature commit shipped the behaviour they had just rejected, offering to fix it afterwards.

**Why:** an in-flight workflow — a commit, a review, a checklist — creates real pressure to fold new work into it as a follow-up, because the workflow has its own momentum and its own next step. That is backwards: the workflow serves the work. A commit is the worst thing to defer to, because it makes *shipping the superseded version* look like progress.

**How to apply:**
- When a design question closes, build it before resuming whatever was in progress. If the in-flight thing is a commit, pause it — the change set is better for having the decision in it than for being fast.
- Recording the decision is worth doing *as well*, never *instead*. A memory entry saying "we decided X" beside code that does not-X is worse than no entry.
- Only defer when the user says to defer. "Let's do it the straightforward way first" is a decision about *scope*, not an instruction to postpone.
- The tell: proposing to commit something you would immediately have to change. If the next sentence out of your mouth is "…and I'll fix that in a follow-up", stop and fix it now.

Related: [[feedback_no_unsolicited_data_fixes]], [[feedback_post_iteration_cleanup]].
