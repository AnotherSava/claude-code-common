---
created: 2026-09-24 15:16:06
platform: macos
---

# Decide whether to walk /adopt across this Mac's other repos

The dotfiles repo records convention v11 (`011-cotenant-hostnames`, adopted in 99f11cf), but every repo adopts independently and each records its own integer in its committed `.claude/conventions`. The tauri-dashboard session reported its repo still records 10, and suspects other repos on this Mac are in the same position — nothing has enumerated them.

The SessionStart hook prints the gap once per session in whichever repo is opened, so a repo nobody opens stays behind silently, with no other surface reporting it.

Work: enumerate the repos on this Mac that carry a `.claude/conventions` file, read each number, and decide which need the pending versions walked. `/adopt` must run in the repo that is behind, by the session that owns it, so the outcome is a routing decision rather than something to run from the dotfiles repo.

Mirror of the memo that parks the same question for the Windows box.
