---
created: 2026-10-27 15:51:38
---

# Make skills load in manual mode where their brace-bearing Context probes are refused

In manual permission mode, invoking a skill fails before it runs when one of its `!` Context probes holds an unquoted `@{upstream}`: 'Shell command permission check failed for pattern ... git rev-list --count HEAD..@{upstream} ...: Brace expansion (unquoted { in concatenation with ,/..)'. Seen 2026-10-27 on Windows during a /wrap-up, from the /commit skill, which has since been removed; /yolo and /wrap-up keep their `@{upstream}` uses in process steps, which are not affected. In auto mode the same probes are handed back to be run as numbered commands instead, so the skills work there.

Probes still carrying the shape: claude/skills/adopt/SKILL.md (the two "commits it is behind its upstream" lines, `git log --oneline HEAD..@{upstream}`), claude/skills/reset/SKILL.md ("Unpushed commits", `git log @{upstream}..HEAD`) and claude/skills/pr-prepare/SKILL.md (four `@{upstream}..HEAD` lines). The skill guidance in claude/skills/skill/SKILL.md, under "No command substitution", still recommends `git log @{upstream}..HEAD` in `!` commands, against pull/SKILL.md and the skill-context-evaluator learning.

Next step: rewrite each so the permission check accepts it in manual mode (quote the ref, or move the probe into a process step as /pull already does), correct the skill guidance, then load each skill in manual mode to confirm.
