---
name: plan-ralphex
description: Create an implementation plan for a new feature, refactor, or fix. Guides an interactive design discussion and produces a structured plan document.
allowed-tools: Read, Glob, Grep, Agent, AskUserQuestion
---

# Create Implementation Plan

Create a structured implementation plan in `docs/plans/` following the project's established format. The plan captures design decisions, file changes, and task breakdown before any code is written.

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

Read all sample plans from `.claude/skills/plan-ralphex/samples/` to learn the established format and level of detail. Then read 2–3 completed plans from `docs/plans/completed/` (if any exist) to pick up project-specific conventions.

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

## Step 5: Confirm with the user

Show the plan and ask if they want any changes before writing it to disk.

## Completion

The end goal of this skill is a plan document in `docs/plans/`. Once the user approves the plan and it is written to disk, the skill is **done**. Do NOT offer to execute the plan, start implementation, or invoke any other skill (e.g. ralphex) to carry out the plan.
