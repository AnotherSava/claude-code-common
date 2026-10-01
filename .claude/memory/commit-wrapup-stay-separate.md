---
name: commit-wrapup-stay-separate
description: Merging /commit into /wrap-up was proposed and rejected 2026-09-30 — they are already composed, and the overlap the proposal assumed does not exist
metadata:
  type: project
---

Merging the `commit` and `wrap-up` skills was proposed on 2026-09-30 and rejected. Do not re-propose it.

They are already composed rather than duplicated. `wrap-up` step 7 runs `/commit`, and its step 4 filter carries an explicit list of concerns it defers to that skill. Across 72 sessions holding either: 53 `/wrap-up` invocations, 65 `/commit`, and 44 of the wrap-up sessions never typed `/commit` at all — because wrap-up ran it for them. Only 4 are an adjacent `commit → wrap-up` pair.

The overlap the proposal rested on is not there. `wrap-up` digests the transcript *file* through `scripts/session_scan.py`; `/reflect` scans the live conversation already in its context, and its `gather-context.sh` reads `MEMORY.md` rather than any transcript. Two different inputs through two different mechanisms, with nothing to extract into a shared scanner.

Merging would also reverse the on-invoke cost work done the same day: a combined skill is roughly 9,400 words loaded whenever somebody wants only a commit, against `/commit`'s 13.5k tokens measured alone.

What was real in the proposal shipped instead. "Revisit existing unpushed commits with the same scrutiny as new changes" named a genuine hole — nothing examined a commit made outside the skill — and that became `/commit` step 1's unpushed-commit audit, `change_scope.py` reading `@{upstream}..HEAD`, and the message check in the `pre-push` hook. The one piece left undone is a guard so a second `/commit` in the same session does not repeat `/reflect`; that is in `wrap-up` step 7.
