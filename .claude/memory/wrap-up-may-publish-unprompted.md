---
name: wrap-up-may-publish-unprompted
description: wrap-up's allowed-tools deliberately pre-authorizes bash scripts/publish.sh, so inside that skill an outward publish runs with no permission prompt and only the skill's own prose gates it
metadata:
  type: project
---

The `allowed-tools` line in `claude/skills/wrap-up/SKILL.md` lists `Bash(bash scripts/publish.sh)` and `Bash(bash scripts/deploy.sh)`, so inside `/wrap-up` those two commands run without a permission prompt.

Measured 2026-10-09: `claude/settings.json` carries no deploy or publish rule in `allow`, `ask` or `deny`, and `permissions.defaultMode` is `auto` — so outside the skill that publish would prompt, and the harness gates nothing here. The skill's own instruction to ask for the verb by name before publishing is the only gate on an outward ship.

The user was shown that reading and kept the entry. Do not propose removing it again, and do not read it as an oversight when auditing the frontmatter: the gate was moved from the harness into the skill's prose on purpose.

What stays unmeasured: `autoMode.soft_deny` names only a "Push to GitHub" rule beside a `$defaults` token the file does not expand, so whether anything in `$defaults` still catches an outward publish was never established.
