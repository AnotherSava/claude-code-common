---
name: Build multiline commit messages with -m flags
description: Use repeatable git commit -m flags for multiline messages, not here-strings — the Bash tool is Git Bash and takes PowerShell here-string syntax literally.
type: feedback
---

When creating a commit with a subject + body, pass them as repeatable flags: `git commit -m "subject" -m "body paragraph"`. Each `-m` becomes its own paragraph. Do NOT build the message with a here-string.

**Why:** The Bash tool on Windows is **Git Bash**, but PowerShell is also available as a separate tool — it's easy to reach for the wrong shell's syntax. A PowerShell single-quoted here-string (`@'…'@`) is not bash syntax; Git Bash treats `@'` and `'@` as literal text, so the `@` characters leak into the commit subject/body. This happened during a `/commit` run and required a `git commit --amend` to fix.

**How to apply:** For commit messages (and other multiline native-command args), prefer multiple `-m` flags — robust across shells and free of quoting/here-string pitfalls. If a genuine bash here-doc is needed, use `<<'EOF' … EOF` (bash syntax), never the PowerShell `@'…'@` form, inside the Bash tool. Related: [[feedback_user_run_commands_bang_prefix]].
