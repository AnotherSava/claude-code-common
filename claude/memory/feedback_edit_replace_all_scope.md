---
name: feedback-edit-replace-all-scope
description: Edit replace_all is only safe when every match shares the same indentation/scope; verify before using or fall back to per-occurrence edits
metadata:
  type: feedback
---

`Edit` with `replace_all: true` is only safe when every match shares the same surrounding indentation and scope context. If the matches live in different blocks (function body vs. nested `with`/`if`/`try`), use separate `Edit` calls instead — `replace_all` will insert the identical new text into both, and any multi-line `new_string` will mis-indent in at least one location.

**Why:** During a MakerWorld script refactor I used `replace_all` to bump `truncated_name = name[:50]` → `truncated_name = name[:100]` and add an `if len(name) > 100: print(...)` warning. The original `name[:50]` appeared in two locations: one at 4-space indent (function body) and one at 8-space indent (inside `with sync_playwright()` + inside `if title_input:`). The same multi-line replacement worked for the 4-space context but collapsed the nested `if title_input:` block at the 8-space context — the new `if len(name) > 100:` line ended up at the same indent as the outer `if title_input:`, silently changing control flow. The "Setting model name" print never fired and the title update was skipped. Took several minutes of "why isn't this saving?" debugging to find.

**How to apply:**
- Before using `replace_all`, run `Grep` with `output_mode: "content"` and a few lines of context to confirm every match sits in compatible scope.
- If indentation or scope differs between matches, prefer per-occurrence `Edit` calls (with extra context in `old_string` to disambiguate).
- Single-line replacements (`name[:50]` → `name[:100]` *alone*) are usually fine across scopes — the risk is specifically with multi-line `new_string` that has internal structure expecting a particular outer indent.
- After a `replace_all` that adds structure, eyeball both call sites with `Read` to confirm indentation is intact.
