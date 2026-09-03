---
name: feedback_codify_conventions_as_single_rules
description: When codifying a convention in a skill, make it one unambiguous rule and sweep all artifacts — no "or this alternative is also fine" escape hatch
metadata:
  type: feedback
---

When adding a formatting/style convention to a skill, state it as a single unambiguous rule and apply it uniformly across every existing artifact. Avoid "X (Y is also acceptable)" wording.

**Why:** In the release skill I wrote breaking changes as "`### ⚠️ Breaking changes` (own `## Breaking change` section is also fine for a major release)". That optional alternative is exactly what let me leave one release on the old plain heading while every other used the emoji one — the user had to catch it. An either/or clause in a convention invites drift.

**How to apply:** Pick one form when codifying. If a real exception exists, scope it with an explicit trigger, not a vague "also fine." After codifying, sweep existing artifacts so they all match the rule. See [[feedback_follow_skill_instructions]].

The sweep has to cross repo boundaries, and a one-time sweep is not enough — ship a detection command inside the skill so a later run can find the old form on its own. The `/transcrypt` skill prescribed `-text` on its crypt rule until 2026-08-04; the correction swept its own repo and stopped there, so printlab — set up three weeks before the fix — churned an encrypted file across two machines for seven more weeks, with the skill's text correct the whole time. Surface the hits and let the user decide rather than silently editing other repos; a stale config line is a live defect that keeps re-manifesting, not the historical record that [[feedback_no_unsolicited_data_fixes]] tells you to leave alone.
