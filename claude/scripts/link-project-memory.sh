#!/usr/bin/env bash
#
# link-project-memory.sh — make a project's Claude memory version-controlled.
#
# Claude Code writes project-specific memory to a machine-local cache:
#   ~/.claude/projects/<project-id>/memory/
# That folder is NOT version controlled, so the knowledge is invisible from
# other machines and lost if the cache is cleared.
#
# This script redirects that cache folder, via a symlink, to a committed
# directory inside the project repo:
#   <repo>/.claude/memory/   (tracked by git, travels with `git clone`)
#
# The harness keeps reading/writing the same cache path, so auto-recall still
# works — the files just live in the repo now. Mirrors the trick that already
# keeps global memory safe (~/.claude/memory -> dotfiles repo).
#
# Re-run safe (idempotent). Run once per project per machine:
#   bash ~/.claude/scripts/link-project-memory.sh [project-path]
# With no argument it uses the current git repo root.

set -euo pipefail

# --- Resolve the project repo root and its Claude project ID ----------------
# Mirror gather-context.sh EXACTLY so the computed ID matches the cache dir the
# harness actually uses: logical path (not `pwd -P`), mangling :/\\ each to one
# dash. See skills/skill/references/claude-project-memory-paths.md.
target="${1:-.}"
cd "$target" 2>/dev/null || { echo "error: cannot enter '$target'" >&2; exit 1; }
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd -W 2>/dev/null || pwd)"
if [ -z "$repo_root" ]; then
  echo "error: '$target' is not inside a git repository" >&2
  exit 1
fi
project_id="$(printf '%s' "$repo_root" | sed 's|[:/\\]|-|g')"

cache_parent="$HOME/.claude/projects/$project_id"
cache_mem="$cache_parent/memory"
repo_mem="$repo_root/.claude/memory"

mkdir -p "$repo_mem"

# --- Migrate any files already sitting in the un-versioned cache ------------
if [ -e "$cache_mem" ] && [ ! -L "$cache_mem" ]; then
  shopt -s dotglob nullglob
  moved=0 skipped=0
  for f in "$cache_mem"/*; do
    base="$(basename "$f")"
    if [ -e "$repo_mem/$base" ]; then
      echo "  skip (already in repo): $base" >&2
      skipped=$((skipped + 1))
    else
      mv "$f" "$repo_mem/$base"
      moved=$((moved + 1))
    fi
  done
  shopt -u dotglob nullglob
  rmdir "$cache_mem" 2>/dev/null || echo "  note: $cache_mem not empty, left in place" >&2
  echo "  migrated $moved file(s), skipped $skipped"
fi

mkdir -p "$cache_parent"

# Keep the committed dir present on a fresh clone even when empty.
if [ -z "$(ls -A "$repo_mem")" ]; then
  : > "$repo_mem/.gitkeep"
fi

# --- Point the cache folder at the committed repo directory -----------------
# On Windows, `ln -s` from Git Bash silently makes a *copy*, not a link — never
# use it (see CLAUDE.md). Emit a directory-junction command to run instead.
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    link_win="$(cygpath -w "$cache_mem" 2>/dev/null || echo "$cache_mem")"
    target_win="$(cygpath -w "$repo_mem" 2>/dev/null || echo "$repo_mem")"
    echo "migrated files into: $repo_mem"
    echo
    echo "Windows: bash can't create the link safely. Run this (no admin needed):"
    echo "  cmd //c mklink /J \"$link_win\" \"$target_win\""
    exit 0
    ;;
esac

if [ -L "$cache_mem" ] && [ "$(readlink "$cache_mem")" = "$repo_mem" ]; then
  : # already linked correctly
else
  if [ -e "$cache_mem" ] || [ -L "$cache_mem" ]; then
    rm -f "$cache_mem"
  fi
  ln -s "$repo_mem" "$cache_mem"
fi

echo "linked: $cache_mem -> $repo_mem"
echo "commit  $repo_mem  in the '$(basename "$repo_root")' repo to share it."
