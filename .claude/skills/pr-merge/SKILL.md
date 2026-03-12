---
name: pr-merge
description: Merge a PR locally with fast-forward to preserve GPG-signed commits, then clean up.
allowed-tools: Bash(git status*), Bash(git log*), Bash(git diff*), Bash(git fetch*), Bash(git checkout*), Bash(git rebase*), Bash(git merge*), Bash(git push*), Bash(git branch*), Bash(git rev-parse*), Bash(git symbolic-ref*), Bash(git stash*), Bash(git remote*), Bash(gh pr *), Read
---

# Merge PR Locally (Preserving GPG Signatures)

Merge a GitHub PR into main using a local fast-forward merge so the original
GPG-signed commit(s) land on main with their signatures intact. GitHub's merge
UI re-creates commits with GitHub's own key, losing the author's GPG signature
and showing "Unverified" on repos that enforce signing.

## Arguments

Optional: PR number or branch name. If omitted, auto-detect from the current
branch or find the single open PR.

## Workflow

### Step 1: Identify the PR

1. If a PR number was given as argument, use it directly.

2. If a branch name was given, find its PR:
   ```
   gh pr list --head <branch-name> --json number,title,state --jq '.[0]'
   ```

3. If no argument was given, try the current branch:
   ```
   git rev-parse --abbrev-ref HEAD
   ```
   If not on main, look up its PR. If on main, list open PRs and pick the
   single one (ask the user if there are multiple):
   ```
   gh pr list --state open --json number,title,headRefName
   ```

4. Fetch PR details:
   ```
   gh pr view <number> --json number,title,state,headRefName,baseRefName,commits,reviews,statusCheckRollup
   ```
   Abort if the PR is not open or if checks are failing.

### Step 2: Verify readiness

1. Confirm the PR has passing checks (or no required checks).
2. Show the PR title, branch, and commit count to the user.
3. Verify all PR commits are GPG-signed:
   ```
   git fetch origin <branch-name>
   git log origin/main..origin/<branch-name> --format="%h %G? %s"
   ```
   `G` = good signature. Warn if any commit is unsigned (`N`) or has a bad
   signature (`B`).

### Step 3: Stash uncommitted changes

If `git status` shows uncommitted changes (staged or unstaged), stash them
before switching branches:
```
git stash
```
Remember to pop the stash at the end (Step 5).

### Step 4: Fast-forward merge

pr-create already rebases onto main before pushing, so the branch should
be fast-forwardable. If not, rebase first.

1. Ensure main is up to date:
   ```
   git fetch origin main
   git checkout main
   git merge origin/main --ff-only
   ```

2. Fast-forward merge the PR branch:
   ```
   git merge <branch-name> --ff-only
   ```
   If `--ff-only` fails, the branch needs rebasing:
   ```
   git checkout <branch-name>
   git rebase main
   git push --force-with-lease origin <branch-name>
   git checkout main
   git merge <branch-name> --ff-only
   ```

3. Push main:
   ```
   git push origin main
   ```

### Step 5: Clean up

1. Close the PR (GitHub auto-closes it if the commits match, but verify):
   ```
   gh pr view <number> --json state --jq '.state'
   ```
   If still open (rare edge case), close it manually:
   ```
   gh pr close <number>
   ```

2. Delete the remote PR branch:
   ```
   git push origin --delete <branch-name>
   ```

3. Delete the local PR branch:
   ```
   git branch -d <branch-name>
   ```

4. Prune stale remote-tracking references (branches deleted on GitHub but
   still cached locally):
   ```
   git remote prune origin
   ```

5. Delete all other local branches that are fully merged into main:
   ```
   git branch --merged main
   ```
   Delete any listed branches other than `main` (or `* main`):
   ```
   git branch -d <stale-branch>
   ```

6. If changes were stashed in Step 3, restore them:
   ```
   git stash pop
   ```

7. Report success: show the merged commit(s) on main with signature status:
   ```
   git log --oneline --format="%h %G? %s" -5
   ```
