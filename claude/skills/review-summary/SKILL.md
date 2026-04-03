---
name: review-summary
description: Summarize the ralphex review - analyze progress log, commits, and changes
allowed-tools: Bash, Read, Glob, Grep
---

Analyze the most recent ralphex review and provide a concise summary.

## Context
- Latest progress log: !`ls -t .ralphex/progress/ 2>/dev/null | head -1`
- Unpushed commits: !`git log origin/main..HEAD --oneline`
- Working tree status: !`git status --short`

## Steps

1. **Find the review progress log**: Look in `.ralphex/progress/` for the most recently modified file. Read it fully.

2. **Identify committed but not pushed changes**: Run `git log origin/main..HEAD --oneline` to find unpushed commits. Then run `git diff origin/main..HEAD` to see the actual changes.

3. **Analyze and summarize**: Based on the progress log and the commits, provide a summary with these sections:

   ### Review Summary
   - **What was reviewed**: Bulleted list of the features/changes under review
   - **Confirmed findings** (fixed): List each real issue found and what was done to fix it
   - **Unaddressed concerns**: List any bugs, concerns, or suggestions that were raised but not fixed and not dismissed as false positives. Omit this section if there are none.
   - **False positives** (discarded): List findings that were evaluated and rejected, with brief reason
   - **Remaining uncommitted changes**: If any, describe them

Keep the summary concise and factual. Focus on what matters: what was found, what was fixed, what was dismissed and why. Use bulleted lists (not numbered) throughout.