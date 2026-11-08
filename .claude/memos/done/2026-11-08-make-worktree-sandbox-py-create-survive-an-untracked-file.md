---
created: 2026-11-08 08:26:34
---

# Make worktree-sandbox.py create survive an untracked file the repo's pre-commit hook refuses

Reported by the what-is-next session 2026-11-08. During review-auto's docs-relevance polish in what-is-next, worktree-sandbox.py create built its carry-in scratch commit by staging every untracked file, including config/deploy.env. The repo's pre-commit hook refuses that path ('refusing to add config/deploy.env in a repo below convention 017 ... Run /adopt'), create errored twice, built no sandbox, and the polish fell back to read-only. Any forked docs-relevance or screenshot-relevance pass in such a repo gets no sandbox. Candidate fixes: make the scratch carry-in commit bypass hooks (--no-verify, since it never leaves the sandbox), or skip paths the hook refuses and report them. Next step: read worktree-sandbox.py's carry-in path, reproduce with a scratch repo whose pre-commit hook refuses one untracked file, pick the fix, add a test.
