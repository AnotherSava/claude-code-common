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
#
# On Windows, run it from an elevated shell. Windows refuses to follow a link created by a
# non-administrator, so without elevation this refuses and prints the command rather than
# making one — see the case in learnings/git-bash-windows-symlinks.md.

set -euo pipefail

# --- Resolve the project repo root and its Claude project ID ----------------
# Mirror gather-context.sh EXACTLY so the computed ID matches the cache dir the
# harness actually uses: logical path (not `pwd -P`), mangling every
# non-alphanumeric character to one dash (so `:` `/` `\` `.` `_` each collapse to
# `-`). See skills/skill/references/claude-project-memory-paths.md.
target="${1:-.}"
cd "$target" 2>/dev/null || { echo "error: cannot enter '$target'" >&2; exit 1; }
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd -W 2>/dev/null || pwd)"
if [ -z "$repo_root" ]; then
  echo "error: '$target' is not inside a git repository" >&2
  exit 1
fi
project_id="$(printf '%s' "$repo_root" | sed 's|[^a-zA-Z0-9]|-|g')"

# `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` is how the rest of this repo resolves the state
# directory (identity-check.py, the publish script, the tune-output preflight). A machine
# that relocates it and a script assuming $HOME/.claude disagree silently: the link gets
# made in a directory the harness never opens, so the machine looks wired and is not.
claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
cache_parent="$claude_dir/projects/$project_id"
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
# On Windows, `ln -s` from Git Bash silently makes a *copy*, not a link, and
# `cmd //c mklink` mangles its `/J` switch under MSYS — so create the link via
# PowerShell, and create the same kind the README's install block creates.
#
# What decides whether that link works is elevation, not the kind. Windows refuses to
# follow a reparse point created by a non-administrator — RedirectionGuard, WinError
# 448 — and it refuses a symlink exactly as readily as a junction, so the "junction,
# no admin needed" this branch used to run bought a link some processes will not walk.
# Measured 2026-09-18: all 19 caches it had made on the Windows machine were unreadable
# from a Python launched over SSH, alongside two of the `~/.claude` links, while every
# link installed from an elevated prompt beside them was fine. So this refuses to make
# a link it cannot make properly, and says what to run instead.
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    link_win="$(cygpath -w "$cache_mem" 2>/dev/null || echo "$cache_mem")"
    target_win="$(cygpath -w "$repo_mem" 2>/dev/null || echo "$repo_mem")"
    ps_link="New-Item -ItemType SymbolicLink -Path '$link_win' -Target '$target_win'"

    # Idempotent, but only for a symlink: a junction from an older run of this script
    # also reads back as a symlink to `[ -L ]`, and re-running is how one gets replaced.
    # readlink yields a POSIX path (lowercased drive, maybe trailing slash), so normalize
    # both sides to Windows form before comparing. What this cannot see is a symlink that
    # was itself made without elevation — indistinguishable from a good one here, and left
    # alone; `check-install.py` is what reports the ones under `~/.claude`.
    link_type="$(powershell -NoProfile -Command "(Get-Item -LiteralPath '$link_win' -Force).LinkType" 2>/dev/null | tr -d '\r')"
    if [ "$link_type" = "SymbolicLink" ] && [ "$(cygpath -w "$(readlink "$cache_mem")" 2>/dev/null)" = "$target_win" ]; then
      echo "already linked: $cache_mem -> $repo_mem"
      exit 0
    fi

    if [ "$(powershell -NoProfile -Command "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)" 2>/dev/null | tr -d '\r')" != "True" ]; then
      echo "error: this shell is not elevated, and a link made without elevation is one" >&2
      echo "       Windows can refuse to follow (WinError 448). Nothing was changed." >&2
      echo "       Run this in PowerShell as Administrator, then re-run this script:" >&2
      echo "         $ps_link" >&2
      exit 1
    fi

    # Clear a stale junction/symlink. Never force-delete a populated dir —
    # migration above leaves one only when files collided, which must be kept.
    if [ -L "$cache_mem" ]; then
      rm -f "$cache_mem"
    elif [ -d "$cache_mem" ]; then
      rmdir "$cache_mem" 2>/dev/null || { echo "error: $cache_mem still holds files (migration collisions); resolve manually" >&2; exit 1; }
    fi

    if ! powershell -NoProfile -Command "$ps_link" >/dev/null 2>&1; then
      echo "error: could not create the link. Run this in PowerShell as Administrator:" >&2
      echo "         $ps_link" >&2
      exit 1
    fi
    echo "linked: $cache_mem -> $repo_mem"
    echo "commit  $repo_mem  in the '$(basename "$repo_root")' repo to share it."
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
