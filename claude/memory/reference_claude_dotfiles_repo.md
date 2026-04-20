---
name: Claude dotfiles repo (D:/projects/claude)
description: ~/.claude/ config, global git files, and hooks are symlinked from a shared dotfiles repo; edits land there and are version-controlled
type: reference
---

`D:/projects/claude/README.md` is the authoritative setup reference for this machine's global Claude Code + git config.

**Symlinked from `~/.claude/`**: `CLAUDE.md`, `settings.json`, `skills/`, `hooks/`, `learnings/`, `memory/`.

**Symlinked from `~/`**: `.git-hooks/` → `git/hooks/`, `.gitignore`, `.gitattributes`. Git is configured globally (`core.hooksPath`, `core.excludesFile`, `core.attributesFile`) to pick these up.

**Implications when editing any of these paths**:

- Changes are version-controlled in the dotfiles repo — not machine-local. Treat them like any other commit: run tests, plan commits, etc.
- Conventions that apply broadly (new skill, new global hook, new learning, global CLAUDE.md edits) belong in the dotfiles repo, not the project at hand.
- Don't hardcode machine-specific absolute paths in symlinked files. Use user-scope `CLAUDE_<APP>` env vars for external paths (e.g. `$CLAUDE_AI_AGENT_DASHBOARD`). Set via PowerShell `[Environment]::SetEnvironmentVariable('CLAUDE_<APP>', 'D:/path', 'User')`. Document each one in the dotfiles README's "External Hook Paths" section.
- The global pre-push hook rejects unsigned commits and Claude-attributed trailers — see memory `reference_push_hook.md` for the resign-ancestors recipe if it fires on a first push.

**NOT symlinked (machine-local)**: `~/.claude.json`. Its `mcpServers[].args` paths are passed straight to `child_process.spawn()` with no shell expansion, so absolute paths are required there — env-var substitution doesn't work.
