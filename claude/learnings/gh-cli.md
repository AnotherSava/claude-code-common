# gh CLI

## `gh issue list` / `gh pr list` resolve a fork to its upstream parent

Run inside a fork that has an `upstream` remote, `gh issue list` (and `pr list`, `issue view`, etc.) auto-resolves to the **parent** repo, not your fork — so it reports the upstream's issues. This is silent and easy to miss.

**Fix:** pin the repo explicitly to your origin: `gh issue list --repo OWNER/REPO …`. Derive `OWNER/REPO` from the origin URL rather than relying on cwd resolution:

```bash
slug=$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##; s#/$##')
gh issue list --repo "$slug" --state open --json number
```

A fork with issues disabled returns the message *"the 'OWNER/REPO' repository has disabled issues"* — handle that as "no issues" (blank/zero), not an error.

Discovered building the `github-status` skill's open-issue count: `InverseCSG` (fork of `yijiangh/InverseCSG`) showed the upstream's issue count until the query was pinned to `AnotherSava/InverseCSG`.
