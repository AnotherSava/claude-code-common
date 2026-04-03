---
name: pr-prepare
description: Analyze the most recent completed plan against its progress log and unpushed commits to produce a plan-vs-implementation divergence summary.
allowed-tools: Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git symbolic-ref:*), Bash(git branch:*), Bash(ls:*), Read, Glob, Grep
---

# PR Preparation: Plan vs Implementation Summary

Analyze whether the final implementation matches the plan, surfacing divergences, unplanned decisions, and missed plan items.

## Context
- Unpushed commits: !`git log origin/main..HEAD --oneline`
- Changed files: !`git diff origin/main..HEAD --stat`
- Latest plan: !`ls -t docs/plans/completed/ 2>/dev/null | head -1`
- Progress logs: !`ls -t .ralphex/progress/ 2>/dev/null | head -5`

## Step 1: Locate the most recent completed plan

Find the most recently modified file in `docs/plans/completed/`. This is the plan to analyze.

## Step 2: Locate the corresponding progress log

The progress log lives in `.ralphex/progress/` and follows the naming convention `progress-{plan-slug}.txt` where `{plan-slug}` matches the plan filename without extension (e.g., plan `2026-03-12-extraction-source-enum.md` → `progress-2026-03-12-extraction-source-enum.txt`).

If there are multiple progress logs matching the slug (e.g., a `-review` variant), read all of them.

## Step 3: Gather implementation data

In parallel:

1. **Read the plan** — extract the design notes, implementation steps, task descriptions, and expected file changes
2. **Read the progress log(s)** — extract what was actually done, any issues encountered, deviations noted
3. **Examine unpushed commits** — run `git log origin/main..HEAD --oneline` to list commits not yet pushed, then `git diff origin/main..HEAD --stat` for a file-level summary, and `git log origin/main..HEAD --format="%h %s%n%b---"` for full commit messages with bodies
4. **Examine the actual diff** — run `git diff origin/main..HEAD` to see the full code changes (use `--no-color` flag)

## Step 4: Analyze divergences

Compare the plan against the actual implementation. Look for:

### A. Plan items not implemented
- Tasks or checklist items from the plan that have no corresponding changes in commits or code
- Files listed in the plan's "Files" sections that were not actually modified or created

### B. Unplanned changes
- Files modified in commits that are not mentioned in the plan
- New types, functions, or modules added that weren't in the plan's design
- Behavioral changes beyond what the plan specified

### C. Design divergences
- Implementation decisions that differ from the plan's Design Notes
- Different type shapes, function signatures, or module boundaries than planned
- Different naming conventions than what the plan specified

### D. Review-driven changes
- Changes visible in commits that appear to be responses to code review feedback
- Look for commit messages referencing "review", "fix", "address", or patterns suggesting iterative refinement after the initial implementation

## Step 5: Output summary

Present a structured summary:

```
## PR Preparation Summary

**Plan**: {plan title}
**Commits**: {count} unpushed commits
**Files changed**: {count}

### Alignment
{Brief statement: does the implementation match the plan overall?}

### Divergences
{List each divergence with:}
- What the plan said
- What was actually implemented
- Whether this seems intentional (improvement) or accidental (oversight)

### Unplanned additions
{List any changes not covered by the plan}

### Missing from plan
{List any plan items that appear unimplemented}

### Review changes
{List changes that appear to stem from post-implementation review}

### Recommendation
{Any concerns that should be addressed before creating the PR, or "Ready to proceed"}
```

## Important

- This skill only **analyzes and reports** — it does NOT modify any files, create commits, or push code
- If there are no unpushed commits, report that and stop
- If the progress log cannot be found, proceed with just the plan and commits
- Be concise — focus on meaningful divergences, not cosmetic differences
