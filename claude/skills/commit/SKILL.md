---
name: commit
description: Analyzes changes and generates Conventional Commit messages
allowed-tools: Read, Glob, Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git log:*), Bash(git reset HEAD:*), Bash(git reset:*), Bash(git ls-files:*), Bash(git rev-list:*), Bash(git rev-parse:*), Bash(git push:*)
---

# Commit Changes

You are tasked with creating git commits for the changes made during this session.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## CRITICAL CONSTRAINT

**The ONLY file changes this skill may make are optimizing imports and updating stale documentation/comments.** Never move, rename, or delete files. Never restructure code. Never modify files to work around `.gitignore` rules. If a file is ignored, it stays ignored — warn the user if you think `.gitignore` needs updating, but do not change it yourself.

## Process:

1. **Assess the current state of the repository:**
   - Read `.gitignore` to know which files should be excluded — changes may come from external editors, IDEs, or other tools, not just this session
   - Run `git status` to see current changes (staged, unstaged, and untracked)
   - Run `git diff HEAD` to see the **total diff against the repo** — this is what actually gets committed
   - Do NOT compare staged vs unstaged to understand changes — that only shows intermediate states. Always compare against HEAD (or the empty tree for new files) to understand the real content of the commit.
   - Cross-check untracked files against `.gitignore` patterns — do not propose committing files that should be ignored (if `.gitignore` is missing entries, warn the user)
   - Review the conversation history (if any) to understand what was accomplished — but do not assume all changes come from this session; the repo state is the source of truth
   - Include ALL uncommitted changes in the plan — both staged and unstaged — unless they match `.gitignore` patterns
   - **Scope guard:** Only commit files that belong to this repository. If earlier work in the conversation touched files in other projects, do not include those changes — each project's commits are handled separately.
   - **Do NOT exit early if there are no uncommitted changes** — step 2 may offer a reset that creates uncommitted changes.

2. **Check for unpushed commits:**
   - First check if an upstream is configured: run `git rev-parse --abbrev-ref @{upstream}` — if this fails (exit code 128), there is no upstream; fall back to `git log origin/$(git rev-parse --abbrev-ref HEAD)..HEAD --oneline` — if that also fails, assume no unpushed commits (e.g. remote doesn't exist yet or branch was just pushed)
   - If upstream exists, run `git log @{upstream}..HEAD --oneline` to list unpushed commits
   - Only if the command **succeeds and produces output** are there unpushed commits — empty output or command failure both mean "no unpushed commits"
   - If there are **no unpushed commits AND no uncommitted changes**, stop — there is nothing to commit.
   - If there are **no unpushed commits but there are uncommitted changes**, skip to the next step.
   - If there **are** unpushed commits, present a numbered list and ask the user to pick one:
     > There are **N** unpushed commit(s) on this branch. What scope should I commit?
     > 1. Uncommitted changes only *(default — skip if working tree is clean)*
     > 2. Reset to `abc1234 commit message` — include this + all above + uncommitted
     > 3. Reset to `def5678 commit message` — include this + all above + uncommitted
     > …
     List commits in **descending** order (most recent first), so each successive option includes more history. The first commit listed resets only the latest commit; the last resets all unpushed commits. If the working tree is clean, omit option 1 and start numbering from the first reset option.
   - **Smart default:** If the most recent unpushed commits form a contiguous run of `fix: address code review findings`, the default (bare Enter) resets all of them (stopping before the first commit with a different message). Otherwise, the default is uncommitted changes only (or the most recent reset if the working tree is clean).
   - Wait for the user's choice:
     - **Uncommitted changes only:** proceed normally with only uncommitted changes
     - **Any reset option:** run `git reset <chosen-commit>~` (soft reset to the parent of the chosen commit), then treat all resulting uncommitted changes as the working set for planning

3. **Optimize imports in modified files**

4. **Update stale documentation and comments:**
   - Read the project README.md (at the repo root) and check if any references to changed paths, APIs, or behavior are stale
   - Check `docs/pages/data-flow.md` (if it exists) and verify it reflects any changes to data flow, message protocols, or control flow logic — use the `/document-data-flow` skill to update it if needed
   - Check comments and docstrings in source files that reference changed behavior, not just the modified files themselves
   - Fix any stale references before proceeding — do not commit code with outdated docs

5. **Confidentiality check:**
   - Scan the diff for content that should not be committed to a public repository: API keys, tokens, passwords, private URLs, internal hostnames, personal data (emails, phone numbers, real names in test data), or proprietary business logic
   - Pay extra attention to learning files (`claude/learnings/`): these are domain knowledge docs meant to be generic and reusable — flag any project-specific details, internal URLs, proprietary names, or customer data that leaked in from the source project
   - If anything looks sensitive, list the findings and ask the user before proceeding — do not silently include them in the commit plan

6. **Plan your commit(s):**
   - Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting and validation rules
   - Group into atomic commits by feature/fix/refactor, make sure that each element can be committed independently
   - Identify which files belong together
   - Put tests and documentation changes in the same commit as the feature they cover, unless there is a significant reason to separate
   - Draft and validate commit messages following the shared rules

7. **Present your plan to the user:**
   - Separate each commit with a unicode line: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
   - For each commit show:
     1. **Commit N**
     2. Commit message with only the type prefix in **bold** (e.g. **refactor**: description), no code block
     3. Number of files and lines changed, then without an empty line in betweem, file list: each file as `inline code` followed by brief description. Pad each file entry with spaces so all entries match the length of the longest one, aligning descriptions into a column.
   - End with: "I plan to create **N** commit(s) with these changes. Shall I proceed?"

8. **Execute upon confirmation:**
   - First, run `git reset HEAD` to unstage everything — this ensures pre-staged files don't leak into the wrong commit
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages using `git commit -S` to GPG-sign them
   - After all commits are done, run `git log @{upstream}..HEAD --format="%h %ai %s"` (with the same fallback logic as step 2) to list all unpushed commits. Format each line as `Mon DD, HH:MM [hash] message` (e.g. `Mar 28, 16:59 [a37da68] feat: add side panel`). Display the full list as the end summary — this gives the user the complete picture of what will be pushed.
   - After showing the summary, ask: "Push?" — if the user confirms, run `git push`.

## Important:
- **NEVER execute commits without explicit user approval.** Invoking `/commit` (even repeatedly) only requests a plan — it is NOT approval to proceed. Wait for a clear "yes", "proceed", or equivalent before running any `git commit` commands.
- Write commit messages as if the user wrote them

## Example output

```
**Commit 1**

**chore**: simplify commit skill, remove script
- Drop format_files.py in favor of inline alignment
- Make skill portable for global use
- Add Claude Code skills section to README

3 files, +7/−35 lines
`claude/skills/commit/SKILL.md`                  Remove script references, simplify formatting
`claude/skills/commit/scripts/format_files.py`   Deleted
`README.md`                                       Add Claude Code skills section
```

## Out of scope:
- Do NOT amend existing commits (soft-reset via step 2 is allowed when user explicitly chooses it)
- Do NOT create or switch branches
- Do NOT move, rename, or delete files
- Do NOT modify `.gitignore` or restructure code to avoid ignore rules

## Remember:
- Changes may come from outside this session (external editors, IDEs, other tools) — do not assume you know what changed; always inspect
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit
