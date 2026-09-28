---
name: feedback_memo_split_dates_from_pickaxe
description: When /adopt v1 Path A splits a memos.md checklist, recover each [x] item's close date from git and offer dated names rather than leaving them undated
metadata:
  type: feedback
---

When conventions v1 (Path A) splits a `.claude/memos.md` checklist, run Path B's pickaxe
(`git log -S"[x] <stamp>" --diff-filter=AM … -- .claude/memos.md`) for every `[x]` item, show each
commit's date and subject beside the memo, and offer to prefix those dates onto the `done/` names.
Path A's default is to leave them undated.

**Why:** In bga-assistant on 2026-09-27, all eight commit subjects matched their memos, and the user
chose dated names. The pickaxe reads a real close from git history, so these dates are not the
invented ones Path A (and v10's step 4) forbid.

**How to apply:** Offer this only when every subject matches its memo. For a subject naming
unrelated work, fall back to a bare slug for that memo. Delete the `.claude/memos.md` checklist only
after the per-item assertion passes.
