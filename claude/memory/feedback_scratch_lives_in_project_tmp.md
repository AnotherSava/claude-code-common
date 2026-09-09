---
name: feedback_scratch_lives_in_project_tmp
description: Scratch artifacts I need to read back go in the repo's gitignored tmp/, never $TEMP — file tools refuse reads outside the working directories
metadata:
  type: feedback
---

Scratch artifacts that have to be re-read — contact sheets, preview renders, corner crops, candidate
comparisons, throwaway HTML — go in the repo's own gitignored `tmp/`. Not `$TEMP`.

**Why:** the file tools refuse reads outside the working directories, so anything written to `$TEMP`
is an artifact I can build and hand over but never open again to check. That breaks the one rule those
artifacts exist to serve, since a contact sheet I cannot look at cannot be verified before it is
linked. Asked on 2026-09-07 whether the read grant could be scoped to just a temp folder: it can
(`/add-dir <path>`, or `--add-dir` at launch), but the path is machine-specific, needs re-adding every
session, and `$TEMP` is shared with every other project on the machine. A project-local `tmp/` needs
no grant at all, behaves identically on the Windows and macOS machines, and cannot collide with
another repo's run.

**How to apply:**
- Add `/tmp/` to the project's `.gitignore` on first use, anchored with the leading slash so it
  matches only the repo root.
- This supersedes the `documentation` skill's `$TEMP/<artifact>-<repo>-<date>` convention for
  anything that must be re-read. That rule's whole purpose was to stop two repos overwriting each
  other's sheet in a shared directory, which is moot once the directory is per-repo. Keep the
  descriptive filename anyway; it costs nothing and reads better in a link.
- Committed text must still never reference these paths — see
  [[feedback_no_scratch_paths_in_committed_code]]. The directory is for artifacts, not for anything
  the repo's own prose points at.
