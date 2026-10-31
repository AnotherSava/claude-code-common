---
name: commit-wrapup-stay-separate
description: /commit was removed 2026-10-31; /yolo and /wrap-up are entry points composed from shared steps, and no top-level skill calls another to commit or push. Supersedes the 2026-09-30 decision to keep commit and wrap-up separate
metadata:
  type: project
---

On 2026-10-31 the `commit` skill was removed. Closing work now has two entry points built from the same shared steps under `claude/skills/shared/`:

- `/yolo` commits everything pending and pushes it, with no review, no reflection and no questions in the normal case. It still runs the privacy scan, the project gate, the message check and the signature.
- `/wrap-up` is the full close-out with one approval: review-auto, the transcript review, the `/reflect` draft, the clean-up passes, grouping and the gate, one summary, then commit and push, then the deploy, publish and release offers.

Which steps are shared, and which of them only `/wrap-up` uses, is listed in README's "Shared Commit and Push Steps" section; `commit.py` is the only place a commit is made. The design is `docs/plans/2026-10-30_23-17-streamline-yolo-and-wrap-up.md`.

**The rule: no top-level skill invokes another to commit or push.** Entry points call shared steps; a step two callers need lives under `shared/`, never inside one caller's SKILL.md. Sub-skills called as units (`/reflect`, `/clean-code`, `/docs-relevance`, `/screenshot-relevance`, `/pull`) stay steps.

**Why:** this replaced the 2026-09-30 decision to keep `/commit` and `/wrap-up` separate, which held that the two were already composed because `/wrap-up` ran `/commit` whole. That coupling was the problem. Each skill had to guess from the transcript what the other had done — `/commit` skipped `/reflect` when it saw an earlier run, `/wrap-up` announced that `/commit` had already run — and every other skill that committed either ran raw `git commit` or handed off to `/commit` and inherited all its gates. Closing a piece of work took four separately invoked skills and about six approvals, and pushing something only to test it cost a full `/reflect`, `/clean-code` and `/docs-relevance` pass.

**How to apply:** do not reintroduce a skill that commits or pushes by calling another top-level skill, and do not add a raw `git commit` to a skill; a check every commit owes goes into `shared/commit.py`, and one every push owes into `shared/push.py`, so every caller gets it. Proposing a single combined commit skill again means re-arguing this decision, not the 2026-09-30 one.
