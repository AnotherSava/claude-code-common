#!/usr/bin/env bash
# Gathers outside-the-project context for the /reflect skill.
# Invoked from the reflect SKILL.md's Context section as a single
# permission-checked command so the user is prompted once instead of
# once per source.
set -u

section() { printf '\n=== %s ===\n' "$1"; }

section global-claude-md
cat "$HOME/.claude/CLAUDE.md" 2>/dev/null || echo "(none)"

section global-memory-index
cat "$HOME/.claude/memory/MEMORY.md" 2>/dev/null || echo "(none)"

# Compute the current project's ID by mangling CWD. See
# ~/.claude/skills/skill/references/claude-project-memory-paths.md
# for the mangling rule and the cross-platform pwd recipe.
cwd="$(pwd -W 2>/dev/null || pwd)"
project_id="$(printf '%s' "$cwd" | sed 's|[:/\\]|-|g')"

section project-id
echo "$project_id"

section project-memory-index
cat "$HOME/.claude/projects/$project_id/memory/MEMORY.md" 2>/dev/null || echo "(none)"

section global-learnings
ls "$HOME/.claude/learnings/" 2>/dev/null || echo "(none)"

section global-skills
ls "$HOME/.claude/skills/" 2>/dev/null || echo "(none)"
