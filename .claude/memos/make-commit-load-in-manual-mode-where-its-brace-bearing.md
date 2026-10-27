---
created: 2026-10-27 15:51:38
---

# Make /commit load in manual mode, where its brace-bearing Context probes are refused

In manual permission mode, invoking /commit fails before the skill runs: 'Shell command permission check failed for pattern ... git rev-list --count HEAD..@{upstream} ...: Brace expansion (unquoted { in concatenation with ,/..)'. Seen 2026-10-27 on Windows during a /wrap-up. In auto mode the same Context probes are handed back to be run as numbered commands instead, so the skill works there. Next step: find every ! probe in claude/skills/commit/SKILL.md (and other skills) whose command holds an unquoted @{upstream} or other brace, and rewrite it so the permission check accepts it in manual mode (quote the ref, or move the probe into a process step as /pull already does), then load /commit in manual mode to confirm.
