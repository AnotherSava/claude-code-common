---
name: plan-ralphex
description: Create an implementation plan for a new feature, refactor, or fix. Guides an interactive design discussion and produces a structured plan document.
allowed-tools: Read, Write, Edit, Glob, Grep, Agent, Skill, AskUserQuestion, Bash(git rev-parse:*)
---

# Create Implementation Plan

Create a structured implementation plan in `docs/plans/` following the project's established format. The plan captures design decisions, file changes, and task breakdown before any code is written.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`

## Working directory

All `docs/plans/` paths in this skill (the new plan file, samples cross-reference, completed plans for convention discovery, the eventual move-to-completed step) are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix Repo root when calling Read/Write/Glob/Grep. Writing `docs/plans/YYYY-MM-DD-slug.md` from a subdirectory creates the file in the wrong place silently.

## Important

- This is an **interactive** process — ask clarifying questions, propose alternatives, and iterate on the design with the user before writing the final plan
- Do NOT write code or make changes to source files — this skill only produces a plan document
- The plan must be detailed enough that it can be executed without re-reading the original discussion

## Step 1: Understand the request

Read the user's description of what they want. If the request is vague or ambiguous, ask clarifying questions before proceeding.

## Step 2: Research the codebase

Explore relevant files to understand:
- Current architecture and patterns
- Which files need modification
- Related existing functionality
- Test patterns in use

Read all sample plans from `~/.claude/skills/plan-ralphex/samples/` to learn the established format and level of detail. Then read 2–3 completed plans from `docs/plans/completed/` (if any exist) to pick up project-specific conventions.

## Step 3: Interactive design discussion

Present your understanding of the problem and a proposed approach. Discuss with the user:
- Design trade-offs and alternatives
- Edge cases and constraints
- UI/UX decisions (if applicable)
- Scope — what's in and what's out

Iterate until the user is satisfied with the approach. Do not rush to write the plan.

## Step 4: Write the plan

Create the plan file at `docs/plans/YYYY-MM-DD-short-slug.md` using today's date. Follow this structure:

```markdown
# Title

## Overview

One paragraph describing what this plan accomplishes and why.

## Context

- Files involved:
  - Modify: `path` — brief description
  - Create: `path` — brief description
- Related patterns: existing code/patterns this builds on
- Dependencies: external requirements (if any)

## Development Approach

- Testing approach: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Design Notes

Document key design decisions, trade-offs, and rationale.
Use bold headers for each topic. Include enough detail that
the reasoning is clear without re-reading the discussion.

**No defensive fallbacks**: Do not design fallback values that mask invalid data (e.g. showing "?" for null ages). Trust input correctness — let invalid values surface as visible `null` or runtime errors rather than silently producing plausible-looking wrong output.

## Implementation Steps

### Task N: Short title

**Files:**
- Modify: `path`
- Create: `path`

- [ ] Step description
- [ ] Step description
- [ ] Write/update tests for ...
- [ ] Run project test suite — must pass before next task

### Task N+1: Verify acceptance criteria

- [ ] Manual test: ...
- [ ] Run full test suite: `npm test`
- [ ] Run linter: `npm run lint`

### Task N+2: Update documentation

- [ ] Update README.md if user-facing behavior changed
- [ ] Update CLAUDE.md if internal patterns changed
- [ ] Move this plan to `docs/plans/completed/`
```

## Step 5: Iterative review with the user

After writing the plan to disk, invoke `/plannotator-annotate` on the plan file so the user can review and annotate it interactively.

1. Run `/plannotator-annotate docs/plans/<plan-file>.md`
2. Address all annotation feedback by editing the plan file
3. Run `/plannotator-annotate` again on the updated plan
4. Repeat until the user approves the plan with no further annotations

Do NOT skip this step or substitute it with a text-based "any changes?" question.

## Completion

The end goal of this skill is a plan document in `docs/plans/`. Once the user approves the plan (no more annotations) and it is written to disk, the skill is **done**. Do NOT offer to execute the plan, start implementation, or invoke any other skill (e.g. ralphex) to carry out the plan.
