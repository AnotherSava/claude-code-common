---
name: feedback_guard_on_version_not_artifact
description: A tool guarding a format someone else defines checks the adopted version, not whether the old artifact still exists
metadata:
  type: feedback
---

When a tool reads a data format that something else defines and versions, guard it on the **version number**, not by sniffing for the shape the format used to have.

Real case (2026-09-15): `memos.py` reads `.claude/memos/` and would list an empty backlog in a repo whose items are still in the `.claude/memos.md` that a convention step replaces. The guard proposed was "refuse when `memos.md` exists". The instruction that replaced it: *"check if repo version is the same or higher of the version with the most recent memo-related changes."*

**Why it is the better rule:**

- **Artifact-sniffing answers for one migration and has to be rewritten for the next.** A version comparison survives the format moving again — the next step declares `affects:` and the guard needs no edit at all.
- **It makes the producer declare the dependency** rather than the consumer guess at it. A step saying "I reshape what `memo` stores" is a fact its author knows; "does `memos.md` still exist" is a consumer inferring that fact from wreckage.
- **It refuses in a repo that is conformant but unrecorded, and that is correct rather than a flaw.** Unrecorded is a different fact from fine, and conflating them is the thing versioning exists to stop. Expect that cost and state it — it means the adoption pass becomes a prerequisite for the tool, once per repo.

**How to apply:** adding a guard to a tool whose format is governed elsewhere, ask "what version last changed what I read?" and compare against what this repo has adopted. Reach for the artifact only when there is no version to ask about. Degrade open, never closed: if the version cannot be determined at all, say so and continue, because a helper that refuses to run when its *governor* is broken is worse than one that proceeds in a repo that turns out to be behind.

Related: [[feedback_not_run_is_not_pass]] — the same instinct one layer down, where the danger is a check that cannot tell a pass from a never-ran. And [[feedback_use_the_tool_you_built]], which is why the repos already in the right shape were made to run the versioned path rather than being grandfathered.
