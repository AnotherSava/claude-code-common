---
name: feedback_pr_with_the_issue
description: An upstream fix that is already written and tested goes up as a PR right after its issue; don't hold it for a maintainer reply
metadata:
  type: feedback
---

When a fix for an upstream project's bug is already written and tested, open the PR right after filing the issue, with the PR body linking the issue (`Fixes #N`). Don't wait for the maintainer to answer the issue first, even where CONTRIBUTING asks a first-time contributor to.

**Why:** the user's words on 2026-10-09: "if PR is already there, maintainer can check the issue and merge PR in one go." A "wait for a reply before writing code" rule exists so nobody builds something the maintainer would refuse. Once the code exists, waiting only adds a round trip, and the worst outcome for the PR is being closed. Example: agwinterm issue #361 and PR #362, opened minutes apart.

**How to apply:** after a confirmed issue post, offer the commit, the push to the fork and the PR as the next step in the same exchange, rather than parking the PR until the maintainer replies. The rule covers only the waiting. Every outward text still needs its own approval, per CLAUDE.md's Outward Communication rule, and a feature whose direction is undecided still goes issue-first.
