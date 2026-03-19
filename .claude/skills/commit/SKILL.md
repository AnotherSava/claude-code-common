---
name: commit
description: Analyzes changes and generates Conventional Commit messages
allowed-tools: Read, Glob, Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git log:*), Bash(git reset HEAD:*), Bash(git ls-files:*)
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

2. **Optimize imports in modified files**

3. **Update stale documentation and comments:**
   - Read the project README.md (at the repo root) and check if any references to changed paths, APIs, or behavior are stale
   - Check `docs/data-flow.md` (if it exists) and verify it reflects any changes to data flow, message protocols, or control flow logic — use the `/document-data-flow` skill to update it if needed
   - Check comments and docstrings in source files that reference changed behavior, not just the modified files themselves
   - Fix any stale references before proceeding — do not commit code with outdated docs

4. **Plan your commit(s):**
   - Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting and validation rules
   - Group into atomic commits by feature/fix/refactor, make sure that each element can be committed independently
   - Identify which files belong together
   - Put tests and documentation changes in the same commit as the feature they cover, unless there is a significant reason to separate
   - Draft and validate commit messages following the shared rules

5. **Present your plan to the user:**
   - Separate each commit with a unicode line: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
   - For each commit show:
     1. **Commit N**
     2. Commit message with only the type prefix in **bold** (e.g. **refactor**: description), no code block
     3. Number of files and lines changed, then without an empty line in betweem, file list: each file as `inline code` followed by brief description. Pad each file entry with spaces so all entries match the length of the longest one, aligning descriptions into a column.
   - End with: "I plan to create **N** commit(s) with these changes. Shall I proceed?"

6. **Execute upon confirmation:**
   - First, run `git reset HEAD` to unstage everything — this ensures pre-staged files don't leak into the wrong commit
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages using `git commit -S` to GPG-sign them
   - Show the result with `git log --oneline -n [number]`

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
`.claude/skills/commit/SKILL.md`                  Remove script references, simplify formatting
`.claude/skills/commit/scripts/format_files.py`   Deleted
`README.md`                                       Add Claude Code skills section
```

## Out of scope:
- Do NOT push to remote
- Do NOT amend existing commits
- Do NOT create or switch branches
- Do NOT move, rename, or delete files
- Do NOT modify `.gitignore` or restructure code to avoid ignore rules

## Remember:
- Changes may come from outside this session (external editors, IDEs, other tools) — do not assume you know what changed; always inspect
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit
