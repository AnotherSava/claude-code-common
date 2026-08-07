---
name: Run the other platform's branch before calling a script done
description: A script with platform-specific branches gets tested only on the authoring OS; actually run the other branch instead of leaving it a print-only stub
type: feedback
---
Shell scripts with platform-specific branches run on both the user's macOS and Windows machines, but are almost always authored on one of them — so the non-authoring branch tends to be under-tested, non-idempotent, or left as a stub that only *prints* what it would do.

**Why:** `link-project-memory.sh` (in the Claude dotfiles repo) shipped a Windows branch that merely printed a `cmd //c mklink` command — which doesn't even work when run from Git Bash, since MSYS mangles the `/J` switch — while the macOS branch was fully functional. It also wasn't idempotent on Windows. Printing a command reads as "implemented" in review; only running it exposes that the command itself is wrong.

**How to apply:**
- When writing or editing a script with platform branches, actually execute the non-authoring platform's path before calling it done. A branch you only reasoned about is not tested.
- Emitting a command for the user to paste is not an implementation — either run it or say plainly that the branch is unimplemented.
- Check idempotency separately per platform; re-running is where the link/junction cases usually diverge.
- For the Windows linking gotchas (PowerShell junctions, cygpath, readlink normalization) see `~/.claude/learnings/git-bash-windows-symlinks.md`, and `~/.claude/learnings/bash-portability.md` for bash-vs-zsh splitting differences.
