---
name: reset
description: Soft-reset unpushed commits back into the working tree for re-committing
allowed-tools: AskUserQuestion, Bash(git log:*), Bash(git reset:*), Bash(git rev-parse:*), Bash(git status:*)
---

# Reset Unpushed Commits

Soft-reset selected unpushed commits back into the working tree so they can be re-committed with `/commit`.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Unpushed commits: !`git log @{upstream}..HEAD --format="%h %ai %s" 2>/dev/null`
- Working tree status: !`git status --short`

## Process

1. If **Unpushed commits** is empty, tell the user there is nothing to reset and stop.

2. **Present options** — show a numbered list:
   > There are **N** unpushed commit(s) on this branch. Which commits should I reset?
   > 1. Reset to `Jun 17, 19:13 abc1234 commit message` — include this + all above
   > 2. Reset to `Jun 17, 18:45 def5678 commit message` — include this + all above
   > ...
   > N. Reset all unpushed commits

   List commits in **descending** order (most recent first). Format timestamps from **Unpushed commits** as `Mon DD, HH:MM`.

   - **Smart default:** If the most recent unpushed commits form a contiguous run of `fix: address code review findings`, the default (bare Enter) resets all of them (stopping before the first commit with a different message). Otherwise, the default is the most recent commit only.

3. **Execute on confirmation:**
   ```
   git reset <chosen-commit>~
   ```
   This is a soft reset to the parent of the chosen commit, putting all changes back into the working tree.

4. **Report result** — show the new working tree status:
   ```
   git status --short
   ```
   Tell the user they can now run `/commit` to re-commit the changes.

## Out of scope
- Do NOT create commits — that is `/commit`'s job
- Do NOT push
- Do NOT switch branches
