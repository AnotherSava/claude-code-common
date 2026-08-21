---
name: feedback_validate_self_gating_edits
description: Never edit a file that gates your own tooling in place — build and validate a candidate copy, then copy it over
metadata:
  type: feedback
---

Never apply an unvalidated edit to a file that gates your own tooling. Blocking `PreToolUse` hooks, git hooks, shell rc files, sandbox/permission config — a mistake in one of these removes the ability to fix the mistake. Build the change in a temp copy, validate it by *executing* the thing it configures, then copy over the original.

**Why:** On 2026-08-21 a `replace_all` on `claude/settings.json` dropped the separating space in `python -S "$HOME/…`, fusing the flag to the path. The file stayed valid JSON, so a syntax check passed — but `doppler-guard.py`, a blocking hook matched on `^(Bash|Write|Edit)$`, began failing on every call, and Bash, Write and Edit all stopped working at once. There was no way to repair it from inside the session; the user had to run a `sed` command themselves. A validity check is not a correctness check: the thing that broke was the *command string*, which JSON knows nothing about.

**How to apply:** Before editing, ask "does this file control whether my tools work?" If yes, never edit in place — `cp` to a temp path, apply the change there with a stream editor, run the configured commands to confirm they work, and only then overwrite. Prefer `sed`/`python` over Edit for files holding `\uXXXX` escapes, which Edit cannot match (see [[unicode-escapes-in-tool-input]]). The specific `replace_all` defect that caused this is recorded in [[feedback_edit_replace_all_scope]]. Related: [[feedback_fix_skills]].
