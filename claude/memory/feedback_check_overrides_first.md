---
name: Find the override before adding a redundant setting
description: When an inherited/global setting appears not to apply, locate the local rule cancelling it and remove that — don't stack another copy of the same setting on top
type: feedback
---
When a global or inherited setting looks like it isn't working, find the **local rule overriding it** before proposing another layer of the same setting.

**Why:** Stacking a redundant setting can mask the symptom while leaving the real defect in place, so it resurfaces on the next file or the next repo — and the override stays to confuse whoever reads the config later. The prompting case: one encrypted file kept churning CRLF↔LF across machines despite a global `* text=auto eol=lf`. The proposed fix was to add `text eol=lf` explicitly; the actual defect was a repo-local `-text` that marked the file binary and cancelled the inherited rule outright. Deleting the override was the whole fix — the global setting had been correct all along.

**How to apply:**
- Ask the tool what the *effective* value is and where it came from before adding anything: `git check-attr`, `git config --show-origin`, `--debug`/`--verbose` resolver flags, `npm config ls -l`.
- Beware settings that resolve to a value that is never consulted — `-text` still reports `eol: lf` in `check-attr` even though binary handling short-circuits it. A displayed value is not proof it applies.
- Prefer deleting the override to adding a counter-setting; reach for an explicit local setting only once nothing is overriding it.
- Detail on this specific case lives in `~/.claude/learnings/git-line-endings.md`; see also [[feedback_verify_before_justifying]].
