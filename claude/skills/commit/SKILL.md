---
name: commit
description: Analyzes changes and generates Conventional Commit messages
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git log:*), Bash(git reset HEAD:*), Bash(git ls-files:*), Bash(git rev-list:*), Bash(git rev-parse:*), Bash(git push:*)
---

# Commit Changes

You are tasked with creating git commits for the changes made during this session.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Ignore rules: !`cat .gitignore 2>/dev/null || true`
- Unstage all: !`git reset HEAD 2>/dev/null || true`
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff HEAD --stat`
- Full diff: !`git diff HEAD`
- Recent commits: !`git log --oneline -10`

## CRITICAL CONSTRAINT

**The ONLY direct file changes this skill may make are through `/clean-code` and `/documentation`.** Never move, rename, or delete source files. Never restructure code beyond what those skills do.

## Process:

**Pacing:** Steps 1–5 are preparation. Sub-skills may legitimately pause when they find substantive changes needing approval (e.g. clean-code proposing dead-code removal, documentation proposing edits). Honor those gates. But when a sub-skill finishes with nothing to report, continue immediately to the next step — do not insert an extra confirmation gate. The only gates the commit skill itself owns are step 6 (plan approval) and step 7 (push).

1. **Assess the current state of the repository** (use Context above):
   - Use **Uncommitted changes**, **Diff summary**, and **Full diff** to understand the total change set against HEAD
   - **Scope guard:** Only commit files that belong to this repository. If earlier work in the conversation touched files in other projects, do not include those changes — each project's commits are handled separately.
   - If there are no uncommitted changes in this repository, stop — there is nothing to commit.
   - Review the conversation history (if any) to understand what was accomplished — but do not assume all changes come from this session; the repo state is the source of truth

2. **Clean code:** Run `/clean-code` to remove debug prints, dead code, duplication, and optimize imports.

3. **Update stale documentation — do this BEFORE planning commits:**
   Run `/documentation` to scan and fix stale references in README, docs, CLAUDE.md, and source comments. All documentation fixes become part of the commit(s) — do not commit code with outdated docs.

4. **Confidentiality check:**
   - Scan the diff for content that should not be committed to a public repository: API keys, tokens, passwords, private URLs, internal hostnames, personal data (emails, phone numbers, real names in test data), or proprietary business logic
   - Pay extra attention to learning files (`claude/learnings/`): these are domain knowledge docs meant to be generic and reusable — flag any project-specific details, internal URLs, proprietary names, or customer data that leaked in from the source project
   - If anything looks sensitive, list the findings and ask the user before proceeding — do not silently include them in the commit plan

5. **Plan your commit(s):**
   - Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting and validation rules
   - Group into atomic commits by feature/fix/refactor — no file belongs to more than one group, and each group can be committed independently
   - Identify which files belong together
   - If a single file contains changes that belong to different commits, do NOT attempt to split it with `git add -p` or partial staging — assign the file to the commit where it fits best and note the mixed content in the plan
   - Put tests and documentation changes in the same commit as the feature they cover, unless there is a significant reason to separate
   - Draft and validate commit messages following the shared rules

6. **Present your plan to the user:**
   - Separate each commit with a unicode line: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
   - For each commit show:
     1. **Commit N**
     2. Commit message with only the type prefix in **bold** (e.g. **refactor**: description), no code block
     3. Number of files and lines changed, then without an empty line in betweem, file list: each file as `inline code` followed by brief description. Pad each file entry with spaces so all entries match the length of the longest one, aligning descriptions into a column.
   - End with: "I plan to create **N** commit(s) with these changes. Shall I proceed?"

7. **Execute upon confirmation:**
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages using `git commit -S` to GPG-sign them
   - After all commits are done, list all unpushed commits with `git log @{upstream}..HEAD --format="%h %ai %s"` (fall back to `origin/<branch>..HEAD` if no upstream). Format each line as `Mon DD, HH:MM [hash] message` (e.g. `Mar 28, 16:59 [a37da68] feat: add side panel`). Display the full list as the end summary — this gives the user the complete picture of what will be pushed.
   - After showing the summary, ask: "Push?" — if the user confirms, run `git push`.

## Important:
- **NEVER execute commits without explicit user approval.** Invoking `/commit` (even repeatedly) only restarts skill execution — it is NOT approval to proceed. Wait for a clear "yes", "proceed", or equivalent before running any `git commit` commands.
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
- Do NOT amend existing commits — use `/reset` to undo unpushed commits first, then `/commit` to re-commit
- Do NOT create or switch branches
- Do NOT move, rename, or delete files

## Remember:
- Changes may come from outside this session (external editors, IDEs, other tools) — do not assume you know what changed; always inspect
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit
