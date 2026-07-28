# Adding a field to many struct literals: the replace_all indentation trap

When you add a field to a struct/record and must update every literal that constructs it (Rust `Foo { .. }`, or any language with brace-delimited literals), a natural move is `Edit(replace_all)` with an *indented* anchor line. This has a subtle failure mode: a shorter-indent pattern matches as a **substring inside deeper-indented lines**.

## The trap

Adding `canary_active: false,` after `instruction_drift: false,` across literals at mixed indentation (12-space test builders vs a 16-space production literal):

```
Edit(replace_all): "            instruction_drift: false,"   (12 spaces)
                →  "            instruction_drift: false,\n            canary_active: false,"
```

The 12-space pattern `            instruction_drift: false,` is a **substring** of the 16-space line `                instruction_drift: false,` (its last 12 leading spaces + the text). So the replace also fires *inside* the 16-space literals, inserting a **second** (misindented) field line → `field specified more than once` (Rust E0062). Running a 16-space pass and then a 12-space pass is worse: the 12-space pass re-hits the 16-space literals the first pass already updated, duplicating.

## Safe patterns

1. **Changing an existing field's value** — replace the **bare** `field: oldval,` (no leading whitespace) with `field: newval,`. The indentation before the match is untouched and no new line is added, so there's no substring collision; one `replace_all` per file handles every indent level cleanly. This is the best option when *renaming/retyping* a field you already added.
2. **Inserting a new field line** — use a **two-line anchor** whose *second* line carries the indentation: `"<indent>prev: x,\n<indent>new: y,"`. The differing indent on the second line breaks the substring match against deeper-indented literals (a 12-space anchor's `\n            new` will not match `\n                new`). Do one pass per indent level.
3. When unsure, edit each literal with a unique multi-line anchor instead of a blanket `replace_all`.

## Signal

Right after a `replace_all` field-add: `missing field X` on some literals **plus** `field X specified more than once` (E0062) on others is exactly this bug — the shorter-indent pass double-inserted into the deeper-indent literals.

Corollary: after a field-add across many literals, always `cargo build` (or the compiler) for the authoritative error list — the editor/LSP diagnostics lag badly across a burst of edits and show stale "missing field" errors on literals that were already updated, which is misleading.
