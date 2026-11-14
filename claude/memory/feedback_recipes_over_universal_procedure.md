---
name: feedback_recipes_over_universal_procedure
description: A skill that must serve varied stacks or cases is written as a recipe book picked by an early step, not one universal procedure
metadata:
  type: feedback
---

When a skill has to work across projects that differ in stack or shape, write it as a set of recipes, one per stack or case, with an early step that settles which case applies and picks the recipe. Do not force one universal procedure over all of them.

**Why:** on 2026-11-13, when the `auth` skill was to gain a step for an app's existing data, the user asked to consider "not a universal single solution for all the cases, but maybe more like a recipe books for different stacks/cases". Asked the same day how to cut the recipes, they chose the cases the existing apps present, which leaves a case no app has yet without a recipe. The four apps surveyed for it each kept people differently: no user records at all, a stub user over tables that already carry a user column, a seeded owner row with roles, and one kept single-admin on purpose. One procedure would have fitted none of them. Reading this as a rule for every skill of that kind is the auth session's interpretation, which the user approved saving on 2026-11-14.

**How to apply:** the procedure is in the skill authoring guide, `~/.claude/skills/skill/SKILL.md`, under "One recipe per case when the subject varies by project": enumerate the real cases by reading the projects, write a recipe only for a case that exists, and keep the shared steps outside the recipes. Related: [[feedback_no_premature_abstraction]], [[feedback_generalize_global_skills]].
