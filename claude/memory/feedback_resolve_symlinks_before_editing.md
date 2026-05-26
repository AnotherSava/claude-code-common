---
name: feedback_resolve_symlinks_before_editing
description: Write/Edit tools fail on symlinks — resolve to real path before editing ~/.claude/ files
metadata:
  type: feedback
---

Write and Edit tools refuse to write through symlinks. All of `~/.claude/` is symlinked from the dotfiles repo (see [[reference_claude_dotfiles_repo]]).

**Rule:** before editing any file under `~/.claude/`, resolve the symlink to its real target path first.

**Why:** the Write/Edit tools error with "Refusing to write through symlink" and the edit is lost. This has happened repeatedly with CLAUDE.md, skills, settings, and memory files.

**How to apply:**
- Use `readlink <path>` (or `realpath`) to get the canonical path, then pass that to Write/Edit.
- On this macOS machine the resolved root is `/Users/olegsavelyev/Projects/claude/claude/` — but always verify with `readlink` rather than hardcoding, since the path differs per machine.
- Symlinked items: `CLAUDE.md`, `settings.json`, `skills/`, `hooks/`, `learnings/`, `memory/`.
- `~/.claude.json` and `~/.claude/projects/` are NOT symlinked — those can be written directly.
