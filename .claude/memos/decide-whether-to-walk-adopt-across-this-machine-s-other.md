---
created: 2026-09-15 09:59:29
platform: windows
---

# Decide whether to walk /adopt across this machine's other repos

A peer session on AIR flagged on 2026-09-15 that /github-status run from the Windows box reports every repo's CONV column as unmeasured, because the adopt skill did not exist in this checkout. It does now, and the dotfiles repo itself is recorded through v13 in .claude/conventions.tsv.

What was never decided is whether to walk /adopt in the OTHER clones on this machine. It was deferred in that session and no answer was ever put to the user.

Worth knowing before starting: until the same day's fix to claude/skills/adopt/steps/memory-cache-symlink.py (bash resolved by absolute path rather than the bare name), convention v4 could not be applied on Windows at all — it failed with 'No such file or directory' for every path form. So any earlier attempt would have stalled there, and the decision only became a real one after that fix.

Start with /github-status to see which clones are behind and by how much, then /adopt per repo. Each repo's decisions land in its own committed .claude/conventions.tsv, so this is safe to do a repo at a time rather than in one sweep.
