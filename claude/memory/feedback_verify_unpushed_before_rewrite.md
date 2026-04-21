---
name: Verify unpushed before rewriting history
description: Check git log @{upstream}..HEAD before amending non-HEAD, rebasing through prior commits, or any history rewrite
type: feedback
---

Before any history-rewriting operation (rebase, amend of a commit that isn't HEAD, reset onto an older sha), run `git log @{upstream}..HEAD --oneline` and confirm **every** commit you plan to rewrite appears in that list. Anything not in that list is already on the remote — rewriting it forces a non-fast-forward push and surprises anyone else who pulled.

**Why:** In the tauri-dashboard session on 2026-04-20 I amended a previously-pushed commit (`c970b11`) via autosquash rebase without checking its push status. The session-start `git status` had already said "Your branch is up to date with 'origin/main'" — the signal was right there. I only verified that my *new* commit was unpushed, then assumed the whole recent history was safe to rewrite. Push was rejected as non-fast-forward, and cleaning up required a force-push.

**How to apply:** When the user asks to amend a non-HEAD commit, squash, rebase, or fixup, the very first step is `git log @{upstream}..HEAD --oneline`. If the target sha isn't there, stop and tell the user: "this commit is already on origin, rewriting it needs a force-push — OK?" before proceeding. Don't conflate "I have unpushed commits" with "recent history is rewritable" — the two are different scopes.
