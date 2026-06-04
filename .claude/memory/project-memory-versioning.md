---
name: project-memory-versioning
description: Project memory is version-controlled via a per-project symlink into the repo; why that won over alternatives
metadata:
  type: project
---

Claude Code writes project memory to an un-versioned machine-local cache
(`~/.claude/projects/<id>/memory/`). `claude/scripts/link-project-memory.sh`
symlinks that cache dir into a committed `<repo>/.claude/memory/`, so memory
survives across machines and `git clone`. Auto-recall keeps working because the
harness reads/writes the same path through the symlink.

**Why per-project symlink over alternatives** (decided 2026-06-03):
- *Centralized in dotfiles repo* — rejected: memory wouldn't ship with the
  project's own clone; couples unrelated projects.
- *Sync script / Stop-hook* — rejected: async, can drift or lose recent edits;
  recall still reads the un-synced cache mid-session.
- *Fold into global memory* — rejected: project-specific facts would load into
  every session's context.
- *Per-project symlink* — chosen: travels with each repo, auto-recall preserved,
  matches the existing per-project `.claude/skills/` commit pattern.

The dotfiles repo keeps two distinct stores: `claude/memory/` is the **global**
payload (deployed to `~/.claude/memory`); the repo-root `.claude/memory/` is this
repo's **project-specific** memory. Don't conflate them. Writing project memory
means resolving the symlink first (Write/Edit refuse to write through symlinks).

**Gitignore interplay** (hit in bga-themes, 2026-06-03): a repo that ignores
`.claude/` keeps the linked memory untracked even after wiring — and git cannot
re-include a path inside a wholly-excluded directory, so `!.claude/memory/` alone
does nothing. Change the ignore entry to `.claude/*` plus `!.claude/memory/`.
