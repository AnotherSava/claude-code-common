---
name: documentation
description: Update stale documentation and comments to match current code
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git status:*)
---

# Update Documentation

Scan project documentation and comments for references that no longer match the code, and fix them.

## Context
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff HEAD --stat`
- Full diff: !`git diff HEAD`
- GH Pages index present: !`test -f docs/index.md && echo yes || echo no`

## Process

1. **Read `README.md`** (at the repo root) and fix any references to changed paths, APIs, or behavior

2. **Read all files in `docs/pages/`** (if the folder exists) and rewrite any sections that no longer match the code — removed features, changed message protocols, new data flows, renamed concepts

3. **Align README with the GH Pages index** — only if **GH Pages index present** is `yes`. Read `README.md` and `docs/index.md` together and reconcile them so they describe the same product at the same point in time:
   - Tagline / one-line description must match (ignoring italics and minor punctuation).
   - The set of user-facing features / supported sites / supported games listed in each must match exactly — no feature appears in one but not the other.
   - Per-feature blurbs in the README must match the intro paragraph of the corresponding `docs/index.md` section (same facts, same scope claims). Wording may differ slightly; facts must not.
   - Install link, beta / access notices, and status blurbs must match.
   - If the README contains per-feature blurbs, each feature link must point to `https://<org>.github.io/<repo>/pages/<feature>` (or `/pages/<product>` in the monorepo variant) and the corresponding `docs/pages/<feature>.md` file must exist.
   - The footer "See full project documentation at …" block in the README must list every page that exists under `docs/pages/` (user-facing pages + Developer guide); no page may be listed that doesn't exist, and no existing user-facing page may be missing.
   - When in doubt about which side is correct, treat `docs/index.md` + `docs/pages/<feature>.md` as the source of truth and update the README to match.

4. **Read `CLAUDE.md`** (project-local `.claude/CLAUDE.md` if it exists, otherwise repo root) and fix any stale file descriptions

5. **Check comments and docstrings** in modified source files (use **Uncommitted changes** and **Full diff** to identify them) that reference changed behavior

6. **Suggest improvements** — if documentation would benefit from a new file or reorganization, suggest it to the user and wait for approval before proceeding

7. **Report** what was updated. If nothing was stale, say so. Call out README ↔ `docs/index.md` mismatches explicitly, even when fixed.

## Out of scope

- Do NOT touch code logic — only comments, docstrings, and doc files
- Do NOT create new documentation files or restructure existing ones without explicit approval
