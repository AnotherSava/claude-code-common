---
name: pr-prepare
description: Analyze progress log, commits, and optionally a plan to summarize what was done, what diverged, and what review found.
allowed-tools: Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(ls:*), Read, Glob, Grep
---

# Preparation Summary

Analyze progress logs and commits to produce a summary covering implementation, review findings, and readiness to proceed. If a related plan exists, include plan alignment analysis.

## Context
- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Unpushed commits: !`git log @{upstream}..HEAD --oneline 2>/dev/null || git log origin/main..HEAD --oneline`
- Unpushed commit details: !`git log @{upstream}..HEAD --format="%h %s%n%b---" 2>/dev/null || git log origin/main..HEAD --format="%h %s%n%b---"`
- Changed files: !`git diff @{upstream}..HEAD --stat 2>/dev/null || git diff origin/main..HEAD --stat`
- Full diff: !`git diff @{upstream}..HEAD 2>/dev/null || git diff origin/main..HEAD`
- Working tree status: !`git status --short`
- Latest plan: !`ls -t docs/plans/completed/ 2>/dev/null | head -1`
- Progress logs: !`ls -t .ralphex/progress/ 2>/dev/null | head -5`

## Step 1: Gather artifacts

1. **Progress log(s)**: Find the most recently modified logs in `.ralphex/progress/`. If there are variants (e.g. `-review`), read all of them. Extract what was done, issues encountered, review findings, and fixes applied.

2. **Plan doc (optional)**: If **Latest plan** is not empty, read it — but only use it if it relates to the work described in the progress log. If the plan is unrelated (different feature, old work), disregard it. Tell the user which plan was found and whether it was used or skipped.

3. **Commits and diff**: Use context data (**Unpushed commit details**, **Changed files**, **Full diff**).

## Step 2: Analyze

If a related plan was found, analyze:
- **Plan alignment**: Which plan items were implemented, which were skipped or deferred
- **Unplanned additions**: Files or behavior not in the original plan
- **Design divergences**: Where implementation differs from planned approach

Based on progress logs and code changes, identify:
- **What was done**: Concrete changes implemented, grouped by area
- **Review findings fixed**: Issues caught during review and resolved
- **Review findings dismissed**: Findings evaluated and rejected as false positives, with reasons
- **Unaddressed concerns**: Issues raised but neither fixed nor dismissed

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

### Review findings
- **Fixed**: {bulleted list of real issues found and resolved}
- **Dismissed**: {bulleted list of false positives with brief reason}
- **Unaddressed**: {bulleted list of open concerns, if any}

### Recommendation
{Any concerns to address, or "Ready to proceed with /reset and /commit"}
```

## Important

- This skill only **analyzes and reports** — it does NOT modify any files, create commits, or push code
- If there are no unpushed commits and no uncommitted changes, report that and stop
- If the progress log cannot be found, proceed with just the commits and diff
- Be concise — focus on meaningful divergences and actionable findings
