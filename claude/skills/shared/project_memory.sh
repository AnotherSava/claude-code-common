#!/usr/bin/env bash
#
# project_memory.sh — the project-memory steps every committing entry point runs before it groups a commit: wire the
# machine-local memory cache into the repo when it is not linked yet, then strip the per-session telemetry the
# harness can write into committed memory files.
#
# One script because `/yolo` and `/wrap-up` both owe these steps before a commit of `.claude/memory/`, and two inline
# copies already diverged once: a split left one entry point without them, so its commits could carry an
# `originSessionId` UUID that conflicts between the two machines' clones.
#
# Usage: project_memory.sh [repo-root]   (defaults to the current git repo root)
# Prints one line for the wiring and one per stripped file. Exits 0 always: a skill's Context runs it, and a failure
# here must not hide the rest of that Context.

repo="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cache=$(bash ~/.claude/scripts/link-project-memory.sh --cache-path "$repo" 2>/dev/null)

if [ -L "$cache" ]; then
  echo "(wired: the cache links into the repo)"
elif [ -n "$(ls -A "$repo"/.claude/memory/*.md "$cache"/*.md 2>/dev/null)" ]; then
  bash ~/.claude/scripts/link-project-memory.sh "$repo" 2>&1
else
  echo "(nothing to wire: no project memory)"
fi

bash ~/.claude/scripts/sanitize-project-memory.sh "$repo" 2>/dev/null
exit 0
