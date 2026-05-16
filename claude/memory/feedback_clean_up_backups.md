---
name: Clean up safety backups proactively
description: After install/migrate/refactor sessions that create *.bak files or backup dirs, delete them once the new state is verified — don't leave them lingering
type: feedback
---

When a workflow creates a temporary safety backup (e.g. `settings.json.bak`, `~/.claude/skills.bak/`, `repo.bak/`), delete it as soon as the new state is verified working. Don't leave it behind for the user to clean up later.

**Why:** User prefers a clean filesystem; stale backups accumulate ambiguity ("is this still needed? safe to delete?"). Said directly during a fresh-machine install: "also delete backup after it is not needed anymore."

**How to apply:**
- Treat backup creation and backup deletion as two halves of the same task — plan both up-front, not "leave it and decide later."
- Verification can be: the new symlink resolves, the new file parses, the replacement command works once. Doesn't need elaborate testing.
- If the new state isn't yet committed and the backup is the only safety net, mention that explicitly and ask before deleting (as with `settings.json.bak` waiting on a commit).
- Applies to any kind of safety copy: file backups, dir backups, snapshot branches, `_old.foo` renames.
