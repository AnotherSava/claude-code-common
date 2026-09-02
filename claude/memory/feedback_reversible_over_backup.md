---
name: feedback_reversible_over_backup
description: Temporarily mutating files for a check? Use a self-inverse edit, not backup-and-restore — backups collide and no-op silently
metadata:
  type: feedback
---

**When temporarily mutating files to run a check, use a reversible transformation — not backup-and-restore.** Backup scaffolding fails silently, and can corrupt the very thing it was protecting.

Two failures in one session, both while inverting `#[cfg(target_os = ...)]` gates to compile the *other* platform's branch:

- Copying `src/agterm.rs` and `src/terminals/agterm.rs` into one flat temp directory **collided on the basename**. The second overwrote the first, so the restore wrote the adapter's contents over the transport module. Caught only by `cmp`-ing the two files afterwards, well after the "restore" had reported success.
- A second attempt used `for f in $FILES` under zsh, which does **not** word-split an unquoted variable. The backup, the edit and the restore all silently did nothing, and the check reported clean without ever having run.

**Why:** both failures produce a *confident pass*. A no-op check and a corrupted restore are indistinguishable from a successful one — the same class of defect as [[feedback_not_run_is_not_pass]], arriving through the scaffolding rather than the check.

**How to apply:**
- Prefer an edit that is its own inverse: `sed -i '' 's/macos/linux/g' …` then `sed -i '' 's/linux/macos/g' …`. No temp state, nothing to collide, nothing left behind if the turn dies mid-way.
- If you must copy, never flatten paths into one directory — two files can share a basename, and in a repo with a `mod.rs`/adapter layout they routinely do.
- Assert the **end state** rather than the restore command's exit code: `cmp` the files that should differ, count the markers that should be gone, re-run the test suite. The restore succeeding says nothing about what it restored.
- Under zsh, `$var` in a `for` list is one word. Use an explicit list or `${=var}`.

Related: [[feedback_not_run_is_not_pass]], [[feedback_post_iteration_cleanup]].
