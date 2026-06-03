---
name: cross-platform-scripts-macos-windows
description: Scripts in claude/scripts run on both macOS and Windows; actually run the Windows branch, don't leave it a print-only stub
metadata:
  type: feedback
---

Shell scripts in `claude/scripts/` are symlinked to `~/.claude/scripts/` and run
on both the user's macOS and Windows machines. They're frequently authored on
macOS, so the Windows branch tends to be under-tested or left as a
non-functional stub.

**Why:** `link-project-memory.sh` shipped with a Windows branch that only
*printed* a `cmd //c mklink` command — which doesn't even work when run from Git
Bash (MSYS mangles the `/J` switch) — while the macOS branch was fully
functional. It also wasn't idempotent on Windows.

**How to apply:** When writing or editing a script with platform-specific
branches, actually run the non-authoring platform's path before calling it done.
For the Windows linking gotchas (PowerShell junctions, cygpath, readlink
normalization) see `~/.claude/learnings/git-bash-windows-symlinks.md`.
