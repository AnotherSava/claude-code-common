---
name: commit
description: Reflects on the session, then analyzes changes and generates Conventional Commit messages
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git log:*), Bash(git reset HEAD:*), Bash(git ls-files:*), Bash(git rev-list:*), Bash(git rev-parse:*), Bash(git push:*), Bash(bash ~/.claude/scripts/sanitize-project-memory.sh:*), Bash(rm:*)
---

# Commit Changes

You are tasked with creating git commits for the changes made during this session.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Ignore rules: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && cat "$R/.gitignore" 2>/dev/null || true`
- Sanitize project memory: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && bash ~/.claude/scripts/sanitize-project-memory.sh "$R" 2>/dev/null || true`
- Unstage all: !`git reset HEAD 2>/dev/null || true`
- Remote ahead by: !`git fetch origin --quiet 2>/dev/null || true; git rev-list --count HEAD..@{upstream} 2>/dev/null || echo "n/a"`
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff HEAD --stat`
- Full diff: !`git diff HEAD`
- Recent commits: !`git log --oneline -10`

## Working directory

`docs/plans/**` paths and any file paths in this skill are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix Repo root when calling Read/Edit/Write/Grep/Glob, and pass paths from `git status --short` to `git add` verbatim (they're already repo-root-relative; git resolves them from cwd up to the repo root automatically).

## CRITICAL CONSTRAINT

**The ONLY direct file changes this skill may make are through `/reflect`, `/clean-code`, and `/documentation`.** Never move, rename, or delete source files. Never restructure code beyond what those skills do. (Exception: untracked junk artifacts like `*.stackdump` may be discarded — see step 1.)

## Process:

**Pacing:** Steps 1–7 are preparation. Sub-skills may legitimately pause when they find substantive changes needing approval (e.g. reflect proposing items to save, clean-code proposing dead-code removal, documentation proposing edits). Honor those gates. But when a sub-skill finishes with nothing to report, continue immediately to the next step — do not insert an extra confirmation gate. The only gates the commit skill itself owns are step 7 (plan-filename warning, if triggered), step 8 (commit-plan approval), and step 9 (push).

1. **Assess the current state of the repository** (use Context above):
   - **Remote sync check (do this first):** If **Remote ahead by** is > 0, the remote has commits you don't have locally and `git push` will be rejected at the end. Surface this to the user immediately and propose `git pull --rebase origin <branch>` before proceeding. Wait for user confirmation before rebasing — it could conflict with the pending changes. After rebasing, re-check `git status --short` since the working tree may differ.
   - Use **Uncommitted changes**, **Diff summary**, and **Full diff** to understand the total change set against HEAD
   - **Scope guard:** Only commit files that belong to this repository. If earlier work in the conversation touched files in other projects, do not include those changes — each project's commits are handled separately.
   - **Discard junk artifacts:** delete untracked crash-dump / junk files that should never be committed — e.g. `*.stackdump` (Git Bash crash dumps on Windows), `core` dumps. Remove them with `rm` so they don't clutter the change set or get staged. Only delete clearly-disposable, never-source artifacts; if an untracked file's purpose is at all unclear, leave it and mention it rather than deleting.
   - If there are no uncommitted changes in this repository, still run step 2 — reflection may produce files worth committing. If the tree is still clean after reflection, stop — there is nothing to commit.
   - Review the conversation history (if any) to understand what was accomplished — but do not assume all changes come from this session; the repo state is the source of truth

2. **Reflect:** Run `/reflect` to extract and persist conversation learnings before they are lost. Skip this step only if `/reflect` already ran in this conversation with no substantive work since — re-running it would just re-scan the same ground. Honor its save-approval gate. **If `/reflect` finds nothing worth saving, immediately proceed to step 3 in the same response — do not stop, do not ask for confirmation.** If any files were saved, re-run `git status --short` and `git diff HEAD` afterwards — the Context snapshot above predates reflection, so the change set may have grown. Files reflect saves outside this repository (e.g. global memory or learnings living in another repo) are excluded by the scope guard — they get committed in their own repo, not here.

3. **Clean code:** Run `/clean-code` to remove debug prints, dead code, duplication, and optimize imports. **If `/clean-code` reports nothing to clean up, immediately proceed to step 4 in the same response — do not stop, do not ask for confirmation.** Only pause if `/clean-code` proposes substantive changes that need user approval.

4. **Update stale documentation — do this BEFORE planning commits:**
   Run `/documentation` to scan and fix stale references in README, docs, CLAUDE.md, and source comments. All documentation fixes become part of the commit(s) — do not commit code with outdated docs. **If `/documentation` reports nothing to fix, immediately proceed to step 5 in the same response — do not stop, do not ask for confirmation.** Only pause if `/documentation` proposes edits that need user approval.

5. **Confidentiality check:**
   - Scan the diff for content that should not be committed to a public repository: API keys, tokens, passwords, private URLs, internal hostnames, personal data (emails, phone numbers, real names in test data), or proprietary business logic
   - Pay extra attention to learning files (`claude/learnings/`): these are domain knowledge docs meant to be generic and reusable — flag any project-specific details, internal URLs, proprietary names, or customer data that leaked in from the source project
   - If anything looks sensitive, list the findings and ask the user before proceeding — do not silently include them in the commit plan

6. **Plan your commit(s):**
   - Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting and validation rules
   - Group into atomic commits by feature/fix/refactor — no file belongs to more than one group, and each group can be committed independently
   - Identify which files belong together
   - If a single file contains changes that belong to different commits, do NOT attempt to split it with `git add -p` or partial staging — assign the file to the commit where it fits best and note the mixed content in the plan
   - Put tests and documentation changes in the same commit as the feature they cover, unless there is a significant reason to separate
   - **Plan files (`docs/plans/**`)**: bundle each plan file into the SAME commit as the implementation it describes. Match by filename slug / content keywords against the changed source paths. Only emit a separate `docs(plans):` commit if the plan file is the ONLY change (e.g. editing a plan mid-design without implementing yet, or archiving unrelated historical plans).
   - Draft and validate commit messages following the shared rules

7. **Validate plan filenames:**
   For every plan file under `docs/plans/` that's part of this change set (new, modified, or renamed — check both `docs/plans/*.md` and `docs/plans/completed/*.md`):
   - Read the file and check whether it contains a top-level `# H1` heading (on any line, outside fenced code blocks).
   - If no H1 is found, warn the user explicitly: the `plan-archive.py` hook derives the filename slug from the plan's H1 and falls back to the original random codename (e.g. `zesty-coalescing-crystal`) when no H1 is present. Suggest a descriptive slug based on the plan's content, offer to rename the file and add an H1, and wait for user confirmation before proceeding. Do not silently include a codename-slug plan file in a commit.
   - If the file starts with the `<!-- plan-archive: no ...` fallback marker comment, treat it the same as a missing H1 — the hook explicitly flagged it. If the user fixes the title, offer to remove the now-stale marker comment in the same edit.

8. **Present your plan to the user:**
   - Separate each commit with a unicode line: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
   - For each commit show:
     1. **Commit N**
     2. Commit message with only the type prefix in **bold** (e.g. **refactor**: description), no code block
     3. Number of files and lines changed, then without an empty line in betweem, file list: each file as `inline code` followed by brief description. Pad each file entry with spaces so all entries match the length of the longest one, aligning descriptions into a column.
   - End with: "I plan to create **N** commit(s) with these changes. Shall I proceed?"

9. **Execute upon confirmation:**
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
- Do NOT move, rename, or delete tracked/source files (untracked junk artifacts like `*.stackdump` are the only exception — discard them per step 1)

## Remember:
- Changes may come from outside this session (external editors, IDEs, other tools) — do not assume you know what changed; always inspect
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit
