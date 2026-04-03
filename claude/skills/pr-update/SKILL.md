---
name: pr-update
description: Soft-reset unpushed commits and use /commit to create clean commits, then push to update an existing PR.
allowed-tools: Bash(git status:*), Bash(git log:*), Bash(git diff:*), Bash(git reset --soft:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git symbolic-ref:*), Bash(git rev-parse:*), Bash(git fetch:*), Bash(git rebase:*), Bash(gh pr view:*), Bash(gh pr edit:*), Read, Glob, Grep
---

# Update Existing PR

Analyze new local changes, soft-reset unpushed commits, then delegate to `/commit` for clean atomic commits. Push the result and update the PR description.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree status: !`git status --short`
- PR details: !`gh pr view --json number,title,url`
- Unpushed commits: !`git log @{upstream}..HEAD --oneline 2>/dev/null`

## Workflow

### Step 1: Gather context

1. Get the current branch name and working tree status:
   ```
   git rev-parse --abbrev-ref HEAD
   git status
   ```
   Abort if on the main branch — there is no PR to update.

2. Verify a PR exists for this branch:
   ```
   gh pr view --json number,title,body,url
   ```
   Abort if no PR is found.

3. Fetch the latest remote state:
   ```
   git fetch origin main
   git fetch origin <branch-name>
   ```

4. Identify the boundary between already-pushed and new changes.
   The remote branch tip (`origin/<branch-name>`) is the baseline —
   everything after it is new. Collect:
   - Unpushed commits:
     ```
     git log origin/<branch-name>..HEAD --oneline
     ```
   - Unstaged and staged changes:
     ```
     git diff --stat
     git diff --cached --stat
     ```
   If there are no unpushed commits AND no uncommitted changes, abort —
   nothing to update.

5. Get the full diff of new changes for analysis:
   ```
   git diff origin/<branch-name>..HEAD --stat
   git diff origin/<branch-name>..HEAD
   git diff
   git diff --cached
   ```

### Step 2: Analyze changes

Review the diffs and unpushed commit messages to understand what was changed and why. Take note of this context — it will inform the `/commit` skill in the next steps.

### Step 3: Soft-reset unpushed commits

Collapse unpushed commits back into the working tree so `/commit` can re-group them into clean atomic commits:
```
git reset --soft origin/<branch-name>
```

### Step 4: Delegate to /commit

Invoke the `/commit` skill. Pass along the context you gathered in Step 2 (what changed, why, relevant commit messages) so it can produce well-informed commit messages. Let `/commit` handle grouping, message drafting, user approval, and commit creation.

### Step 5: Rebase onto main

Ensure the branch is up to date with main:
```
git fetch origin main
git rebase main
```
If the rebase produces conflicts, stop and ask the user to resolve them.

### Step 6: Push

Push the updated branch. Since we reset commits that were already on
the remote, force-with-lease is required:
```
git push origin <branch-name> --force-with-lease
```

### Step 7: Update PR description

1. Read the current PR body:
   ```
   gh pr view --json body
   ```

2. Append an "Update" section to the PR body with a summary of the new
   changes. Use a HEREDOC:
   ```
   gh pr edit --body "$(cat <<'EOF'
   <existing body>

   ## Update: <short description>
   <bullet points summarizing the new commits>
   EOF
   )"
   ```

3. Report the PR URL to the user.

## Important

- **NEVER proceed without explicit user approval** — `/commit` will handle confirmation
- Do NOT push to a different branch or create a new PR
- Do NOT amend the existing remote commits — only reset and recommit new local changes
