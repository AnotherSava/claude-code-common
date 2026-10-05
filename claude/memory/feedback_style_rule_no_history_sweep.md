---
name: feedback_style_rule_no_history_sweep
description: A newly added or tightened style rule applies to new text only — don't sweep existing files for violations, and don't offer to
metadata:
  type: feedback
---

When a phrasing or style rule is added or tightened, apply it going forward and leave the files that already violate it alone. Do not offer a sweep.

**Why:** on 2026-10-04 a banned word turned up 24 times across tracked files, roughly 15 of them genuine, and the sweep was offered as a memo. The user: "2 drop; it's enough if you avoid it from now on, fixing history is not necessary." The cost of the old text is zero — nothing runs on it — while the sweep is a long triage that has to separate real violations from legitimate uses of the same word.

**How to apply:** report the class and its size if it comes up, then stop; no memo, no offer, no edits. This does not contradict CLAUDE.md's **Best-Practice Adoption**, which requires a clean baseline — that governs a rule a *tool* enforces, where every later run fails until the baseline is clean. An unenforced style rule has no run to fail, so existing text costs nothing. Related: [[feedback_no_unsolicited_data_fixes]] is the same reflex over stored data.
