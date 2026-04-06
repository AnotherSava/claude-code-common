---
name: pr-create
description: Prepare commits for the current feature branch, push, and create a PR to main.
allowed-tools: Bash(git status:*), Bash(git log:*), Bash(git diff:*), Bash(git reset --soft:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(git fetch:*), Bash(git checkout:*), Bash(git merge:*), Bash(git rebase:*), Bash(gh pr create:*), Bash(ls:*), Read, Glob, Grep
---

# Create PR for Plan-Based Changes

Prepare commits on the current feature branch, push, and open a PR to main.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree status: !`git status --short`
- Commits ahead of main: !`git log main..HEAD --oneline`

## Workflow

### Step 1: Gather context

1. Use **Current branch** from context. If on `main`, abort — the user must check out the feature branch first.

2. Use **Working tree status** and **Commits ahead of main** from context. Abort if there are no commits ahead of main and no uncommitted changes.

3. Find the latest completed plan doc — look in `docs/plans/completed/` for the most recently created file whose name relates to the current branch or the work described in the commits.

4. Find the matching progress log in `.ralphex/progress/`.

5. Read the plan and progress log to understand the scope and intent of the changes.

### Step 2: Prepare commits

Reset commits back to the working tree and use `/commit` to create clean, atomic commits:

1. Run `/reset` — let the user choose which commits to reset.

2. Run `/commit`. It handles everything: diff analysis, atomic grouping, commit messages, import optimization, doc updates. Pass the plan doc and progress log context so it can write informed messages.

### Step 3: Rebase onto main

Ensure commits are based on the latest main so pr-merge can fast-forward:
```
git fetch origin main
git rebase main
```
If the rebase produces conflicts, stop and ask the user to resolve them.

### Step 4: Push and create PR

1. Push the branch:
   ```
   git push -u origin <branch-name>
   ```
   If the branch was already pushed with the old commits, use `--force-with-lease`:
   ```
   git push -u origin <branch-name> --force-with-lease
   ```

2. Draft the PR description. The PR body should be **more detailed than the commit message** — it is the primary review artifact. Build it from the plan doc, diff, and progress log:

   - **Overview**: 2-3 sentences on what this PR accomplishes and why (from the plan's Overview section)
   - **What changed**: bulleted list of concrete changes grouped by area (new modules, modified behavior, structural changes, test coverage). Derive from the diff, not just the plan — if the implementation added things not in the original plan, include them here.
   - **Design decisions**: key trade-offs and rationale (from plan's Design Notes). Highlight anything a reviewer should pay attention to.
   - **Scope reconciliation**: compare the plan against the actual diff. If the implementation diverged from the plan (added features, dropped features, changed approach), note the differences and why.
   - **Plan reference**: link to the plan document filename
   - **Test coverage**: summary of test files and what they cover

3. Create the PR:
   ```
   gh pr create --base main --title "<commit subject line>" --body "<PR description>"
   ```

4. Report the PR URL to the user.
