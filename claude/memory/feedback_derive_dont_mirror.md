---
name: feedback_derive_dont_mirror
description: Asked to fix how stored state is synced or committed, first check whether it needs to exist — an unverifiable mirror of a third-party system drifts silently
metadata:
  type: feedback
---

When the task is to fix the *lifecycle* of stored state — when to commit it, how to roll it back,
how to remember to update it — check first whether the state needs to exist at all. A lifecycle
problem often disappears along with the field.

**Why:** 2026-09-02. A `cws-publish.json` mirroring Chrome Web Store dashboard data kept blocking
`git pull`, because its `lastPublished` stamp was written after each publish and never committed.
Asked to fix it, I proposed better commit ordering; asked again, I argued about committing early and
rolling back on failure. Only when Oleg asked "do we even need to store this information at all" did
I probe the API — which returns `crxVersion`, the published version, making the stamp redundant —
and check what read the rest, which was nothing. The whole file went away, and with it the commit
ordering, the rollback and the reminder.

**How to apply:** the tell is being asked to improve *synchronisation* — commit timing, a rollback, a
reminder, a staleness check. Before designing any of it, ask two things: is this derivable from
something already authoritative (the live API, git history, the running system), and does any step
actually read it? Be especially suspicious of a mirror of a **third-party system you cannot read
back**: it looks authoritative, nothing can ever validate it, and it drifts the moment someone edits
the source directly — so it fails silently, which is worse than the loud failure (a dirty tree, a 400
at submit) it was meant to prevent.

Cousins: [[feedback_check_the_limit_is_real]] — I said the API couldn't read the listing back and
stopped there, instead of probing what it *could* read; [[feedback_live_values_source_of_truth]] —
never cite a stored snapshot for a value the running system owns; and
[[feedback_extend_schema_not_freetext]], whose converse half is the same test one field at a time: a
field stays only if a step reads it today.
