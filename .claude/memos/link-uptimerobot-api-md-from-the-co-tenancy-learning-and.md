---
created: 2026-10-21 05:15:22
---

# Link uptimerobot-api.md from the co-tenancy learning and note a keyword monitor covers only half the identity rule

From the /docs-relevance pass on commit fb9520c (2026-10-21), two suggestions left out of that commit's scope:

1. claude/learnings/docker-compose-shared-host-co-tenancy.md, "Detect it" section, asks for an off-box identity check but its table lists only identity-check.py, which runs at publish time. An UptimeRobot keyword monitor (claude/learnings/uptimerobot-api.md) does the same check continuously between publishes; add a cross-link.

2. claude/learnings/uptimerobot-api.md should say a keyword monitor covers only one half of the co-tenancy rule: keyword_type=2 asserts the host's own marker is present, but the rule also requires every other tenant's marker to be absent. One monitor watches one keyword_value, so the absent half would need one extra keyword_type=1 monitor per foreign marker. That count is inferred from the file, not checked against UptimeRobot's docs; verify before writing it.
