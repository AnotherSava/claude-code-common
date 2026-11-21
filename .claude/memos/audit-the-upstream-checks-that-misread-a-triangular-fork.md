---
created: 2026-11-20 17:55:05
---

# Audit the @{upstream} checks that misread a triangular fork

In a fork whose branch tracks the third-party upstream while remote.pushDefault is origin (agterm), any check meant to catch the other machine's pushes reads @{upstream} and sees every unmerged third-party commit as 'behind'. /adopt was fixed on 2026-11-20 (fetch the push remote, compare HEAD..@{push} under -c push.default=current); recipe in claude/learnings/git-fork-push-target.md. Still on @{upstream}: the pull skill, github-status (repos-status.py behind/unpushed counts), the idle-gap rule in claude/CLAUDE.md, shared/sync-and-push.md, and the convention version READMEs' 'behind its upstream' advice. Next step: for each, decide whether it means 'the other machine's pushes' (switch to the push target) or 'the tracked branch' (leave), and fix the first kind.
