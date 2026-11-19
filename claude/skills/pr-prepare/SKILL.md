---
name: pr-prepare
description: Analyze commits, and optionally a plan, to summarize what was done, what diverged, and which commits fixed review findings.
allowed-tools: Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(ls:*), Read, Glob, Grep
---

# Preparation Summary

Analyze commits to produce a summary covering implementation, review fixes, and readiness to proceed. If a related plan exists, include plan alignment analysis.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Unpushed commits: !`git log @{upstream}..HEAD --oneline 2>/dev/null || git log origin/main..HEAD --oneline`
- Unpushed commit details: !`git log @{upstream}..HEAD --format="%h %s%n%b---" 2>/dev/null || git log origin/main..HEAD --format="%h %s%n%b---"`
- Changed files: !`git diff @{upstream}..HEAD --stat 2>/dev/null || git diff origin/main..HEAD --stat`
- Full diff: !`git diff --no-textconv @{upstream}..HEAD 2>/dev/null || git diff --no-textconv origin/main..HEAD`
- Working tree status: !`git status --short`
- Latest plan: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && ls -t "$R/docs/plans/completed/" 2>/dev/null | head -1`

## Working directory

`docs/plans/completed/` and any other file paths in this skill are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix Repo root when calling Read/Glob/Grep/ls. Bare paths are cwd-relative.

## Step 1: Gather artifacts

1. **Plan doc (optional)**: If **Latest plan** is not empty, read it — but only use it if it relates to the work described in the commits. If the plan is unrelated (different feature, old work), disregard it. Tell the user which plan was found and whether it was used or skipped.

2. **Commits and diff**: Use context data (**Unpushed commit details**, **Changed files**, **Full diff**).

## Step 2: Analyze

If a related plan was found, analyze:
- **Plan alignment**: Which plan items were implemented, which were skipped or deferred
- **Unplanned additions**: Files or behavior not in the original plan
- **Design divergences**: Where implementation differs from planned approach

Based on the commits and code changes, identify:
- **What was done**: Concrete changes implemented, grouped by area
- **Review fixes**: Commits whose message says they address review findings (such as `fix: address code review findings`). Dismissed findings and open concerns are recorded in none of the artifacts this skill reads, so it does not report them.

## Step 3: Output summary

```
## Preparation Summary

**Plan**: {plan title} (or "No related plan found")
**Commits**: {count} on branch
**Files changed**: {count}

### What was done
{Bulleted list of implemented changes, grouped by area}

### Plan alignment (if plan is present)
{Brief statement: does the implementation match the plan?}
{List divergences — what plan said vs what was built, whether intentional}
{List any unplanned additions}
{List any missing plan items}

### Review fixes
{Bulleted list of the review fixes the commits record, or "None recorded in the commits"}

### Recommendation
{Any concerns to address, or "Ready to proceed with /reset and /wrap-up"}
```

## Important

- This skill only **analyzes and reports** — it does NOT modify any files, create commits, or push code
- If there are no unpushed commits and no uncommitted changes, report that and stop
- Be concise — focus on meaningful divergences and actionable findings
