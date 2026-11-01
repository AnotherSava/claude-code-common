---
created: 2026-11-01 06:55:29
---

# Stop the Node convention rules flagging scratch manifests under a globally ignored tmp/

Reproduced 2026-11-01 in the scheduler repo: an untracked tmp/probe-manifest/package.json that `git check-ignore -q` reports as ignored still fails node-engines (v5) and package-manager-pin (v5) in check.py, so a scratch npm install left in tmp/ fails that repo's commit gate.

Cause: _node.manifests() filters through _git.ignored_untracked(), which keeps only hides whose rule source is a tracked file in the repo. It discards hides from the per-machine global excludes file on purpose, so two machines derive one set from one tree. But /tmp/ is ignored ONLY by the global excludes (git/gitignore installed as ~/.gitignore), per the scratch convention in memory/feedback_scratch_lives_in_project_tmp.md, which tells repos not to add their own entry. The _node.py module docstring names exactly this case (a manifest in a gitignored tmp/ is 'a designed and recurring condition') as what the filter is for, and the filter can never match it.

Options to weigh: exempt the agent-scratch root tmp/ by name in manifests() (it is the agent's convention, defined in the dotfiles, so it is the same on every machine); or have ignored_untracked accept a hide whose source is the global excludes file when the matching pattern is one the dotfiles' git/gitignore ships. Whichever, add a check.py case: untracked tmp/x/package.json, global-only ignore, expect no finding.
