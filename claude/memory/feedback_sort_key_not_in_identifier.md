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
