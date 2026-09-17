---
created: 2026-09-15 09:59:29
platform: windows
---

# Decide whether to walk /adopt across this machine's other repos

A peer session on the macOS machine flagged on 2026-09-15 that /github-status run from the Windows box reports every repo's CONV column as unmeasured, because the adopt skill did not exist in this checkout. It does now, and the dotfiles repo is still the only clone here holding a record at all — every other repo on this machine reads as unadopted because it has no `.claude/conventions` file.

What was never decided is whether to walk /adopt in those other clones. It was deferred in that session and no answer was ever put to the user.

Start with /github-status to see which clones are behind and by how much, then /adopt per repo. A repo's whole convention state is one integer in its own committed `.claude/conventions`, advanced one version at a time as the walk performs each migration, so this is safe to do a repo at a time rather than in one sweep.

The system was rebuilt under this memo on 2026-09-16: one committed record instead of two, no `scope:` field, the memory-cache link moved out of the versions into a universal rule that every repo's commit gate runs, and what were v5 through v15 renumbered to v4 through v14. Nothing had adopted under either numbering, so there is nothing to reconcile — but a number quoted in a session older than that date means a different migration than it does now.
