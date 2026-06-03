#!/usr/bin/env bash
#
# sanitize-project-memory.sh — strip machine-specific telemetry from a
# project's committed Claude memory files before commit.
#
# When `link-project-memory.sh` redirects a project's memory cache into
# `<repo>/.claude/memory/`, the harness keeps writing files there — and
# occasionally injects metadata like `originSessionId: <UUID>` that
# identifies the local Claude conversation. That UUID is machine-local
# noise: meaningless to other contributors, and it changes per-session, so
# every clone would generate a different value and produce deterministic
# merge conflicts.
#
# This script removes those telemetry lines from
# `<repo>/.claude/memory/**/*.md`. Idempotent — running it twice produces
# no further changes. Safe to run unconditionally; exits cleanly when the
# memory dir doesn't exist.
#
# Usage:
#   sanitize-project-memory.sh [repo-root]
#     repo-root defaults to `git rev-parse --show-toplevel` from cwd.
#
# Output: one "stripped: <path> (<n> line(s))" line per changed file,
# nothing otherwise. Exits 0 always (unless given a bad path).
set -uo pipefail

repo="${1:-}"
if [ -z "$repo" ]; then
  repo="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi
if [ -z "$repo" ] || [ ! -d "$repo" ]; then
  echo "sanitize-project-memory: not in a git repo (no repo root given)" >&2
  exit 0
fi

mem_dir="$repo/.claude/memory"
[ -d "$mem_dir" ] || exit 0

# Telemetry keys to strip from frontmatter. Add new keys here as the
# harness introduces them; each pattern matches the entire line including
# any leading whitespace (the keys live nested under `metadata:`).
patterns=(
  '^[[:space:]]*originSessionId:[[:space:]]'
)

# Use `find` instead of `**` so the script runs under bash 3.x (the system
# bash on macOS) without needing `shopt -s globstar`.
while IFS= read -r -d '' f; do
  before=$(wc -l <"$f")
  for p in "${patterns[@]}"; do
    tmp="$f.sanitize.tmp"
    grep -Ev "$p" "$f" > "$tmp" && mv "$tmp" "$f"
  done
  after=$(wc -l <"$f")
  stripped=$((before - after))
  if [ "$stripped" -gt 0 ]; then
    rel="${f#$repo/}"
    echo "stripped: $rel ($stripped line(s))"
  fi
done < <(find "$mem_dir" -type f -name '*.md' -print0)
