---
name: Sort keys live in metadata, not in the name
description: don't bake an ordering into a filename or id — a second sort criterion then costs a mass rename; put it in a field
metadata:
  type: feedback
---

When a value orders a set of things, store it as a **field**, not inside the thing's name or id.

Real case 2026-09-12, designing one-file-per-memo storage: I proposed `2026-09-12-0517-<slug>.md`, arguing the date in the filename gives `ls`, the editor's file tree and `git status` chronology for free, with one home for the fact. Oleg: *"i have a strong feeling that creation date won't stay as the only sorting criteria for long, so let's make it more flexible."* That flipped the design — frontmatter holds `created`, the filename is only a slug.

**Why:** a name is an identifier, and an identifier that encodes an ordering is two facts in one string — the same overloading [[feedback_extend_schema_not_freetext]] and the Explicit State rule reject for object fields. The cost lands later and all at once: adding `priority` or `area` as a second criterion means renaming every file, and re-sorting means renaming them again. A field costs one line and no renames.

**How to apply:** put the ordering in metadata (frontmatter, a column, an attribute) whenever more than one ordering is plausible — which is nearly always. Reserve name-encoded ordering for sets that are genuinely append-only and read by tools you do not control. The convenience given up is real — a bare `ls` no longer shows the order — and is worth less than being locked to one sort.

**Where that reservation has fired, 2026-09-15:** the same backlog's `.claude/memos/done/`, whose files gained a `<close-date>-` prefix when Oleg settled that addressed memos are kept for good rather than deleted. It meets both halves of the clause exactly — nothing removes a done memo, and no command lists one, since `list` and `show` both resolve against the open backlog — so `ls`, a file browser and `git status` are its only readers and a name is the only thing they sort by. The open half of the backlog is unchanged and still carries `created` in frontmatter. Read the two together as the rule and its boundary: the field wins wherever a reader could be given one, and a name is right only where there is no reader to give it to.
