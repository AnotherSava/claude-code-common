---
name: pr-create
description: Squash ralphex commits into a single Conventional Commit, push, and create a PR to main.
allowed-tools: Bash(git status:*), Bash(git log:*), Bash(git diff:*), Bash(git reset --soft:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git symbolic-ref:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(git fetch:*), Bash(git checkout:*), Bash(git merge:*), Bash(git rebase:*), Bash(gh pr create:*), Bash(ls:*), Read, Glob, Grep
---

# Squash Ralphex Commits and Create PR

Squash all commits on the current feature branch into a single Conventional Commit, push, and open a PR to main.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Workflow

### Step 1: Gather context

1. Determine the main branch:
   ```
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
   ```
   Fall back to `main` if the command fails.

2. Get the current branch name and working tree status — ralphex manipulates branches outside of Claude Code, so never assume the branch or status from earlier in the conversation:
   ```
   git rev-parse --abbrev-ref HEAD
   git status
   ```
   **If on the main branch**, ralphex may have already finished and switched back. List recent feature branches to find the right one:
   ```
   git branch --sort=-committerdate
   ```
   Look for a branch that is ahead of main. Ask the user to confirm which branch to use, then check it out:
   ```
   git checkout <branch-name>
   ```
   If no feature branches exist or none are ahead of main, abort.

3. Check if the remote branch has commits already merged to main:
   ```
   git fetch origin main
   git log origin/main..origin/<branch-name> --oneline
   ```
   If the remote branch has commits that are ahead of `origin/main`, these were already pushed from a previous session. Fast-forward main to absorb them before squashing:
   ```
   git checkout main
   git merge origin/<branch-name> --ff-only
   git push origin main
   git checkout <branch-name>
   ```
   Then verify the remaining commits with `git log main..HEAD --oneline` — only these will be squashed.

4. List commits to be squashed:
   ```
   git log main..HEAD --oneline
   ```
   Abort if there are no commits ahead of main.

5. Get the full diff for analysis:
   ```
   git diff main...HEAD --stat
   git diff main...HEAD
   ```

6. Read the project README.md (at the repo root) and check if any references to changed paths, APIs, or behavior are stale. Check `docs/pages/data-flow.md` (if it exists) and verify it reflects any changes to data flow, message protocols, or control flow logic — use the `/document-data-flow` skill to update it if needed. Also check comments and docstrings in source files that reference changed behavior, not just the modified files themselves. Fix any stale references before proceeding.

7. Find the latest completed plan doc — look in `docs/plans/completed/` for the most recently created file whose name relates to the current branch or the work described in the commits.

8. Find the matching progress log in `.ralphex/progress/`.

9. Read the plan and progress log to understand the scope and intent of the changes.

### Step 2: Draft commit message

Read `~/.claude/skills/shared/commit-message-rules.md` for formatting and validation rules.

Compose a commit message following those rules. Analyze the diff, commit messages, plan doc, and progress log to write a meaningful summary. Reference the plan topic in the body.

### Step 3: Confirm with user

Display the full drafted commit message and ask the user to approve or revise it. Do not proceed until the user confirms.

### Step 4: Soft reset and commit

1. Squash all commits:
   ```
   git reset --soft main
   ```

2. Stage everything (ralphex may have left untracked files):
   ```
   git add -A
   ```

3. Create the single GPG-signed commit using a heredoc:
   ```
   git commit -S -F - <<'EOF'
   <approved commit message>
   EOF
   ```

### Step 5: Rebase onto main

Ensure the squashed commit is based on the latest main so pr-merge can
fast-forward without rebasing:
```
git fetch origin main
git rebase main
```
If the rebase produces conflicts, stop and ask the user to resolve them.

### Step 6: Push and create PR

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
