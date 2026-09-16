---
created: 2026-09-15 17:30:28
---

# Give supersedes: a walk-time effect, or say in prose that it has none

Measured 2026-09-15 in this repo while deciding how to fix the Node manifest walk. The supersede route was rejected partly because of this, and the gap stays open for whoever reaches for the mechanism next.

## What was measured

`supersedes:` appears in `conventions.py` in exactly three places: the frontmatter parse, a display mark in `cmd_steps`, and two `selftest` assertions (the named version exists; the superseded step carries a `## Superseded` section). Nothing else reads it.

`pending_steps` is membership alone — a step is pending if the repo holds no line for its version. So a repo short of a superseded step is still walked through that step, ascending, before it ever reaches the correction. `SKILL.md` gives `retracted:` an explicit walk-skip ("A step marked (retracted at vN - record n/a) is not walked") and `cmd_status` prints a matching annotation; `supersedes:` has neither, in prose or in code.

## Why that matters

A superseding step is supposed to correct a step that was wrong. In a repo that has not yet reached the wrong version, the correction arrives *after* the damage: /adopt asks the wrong question, shows the wrong dry run, writes on a yes, records `applied`, and only then walks the step whose job is to undo it. The doctrine assumes a fleet already past the bad version; measured here, 28 of 29 repos are short of v7 onward, so the mechanism is aimed at a population of zero and produces the harm in the population that exists.

`supersedes:` is also a single int — `_int_field` raises `StepError` on "7,8,9", which takes every subcommand to exit 2 and blanks the fleet session-start notice. So three wrong steps need three superseding steps, or one whose frontmatter names one while two others still read as current.

## The decision to make

Three candidates, not equivalent:

1. Give it the same walk-skip `retracted:` has: a step with a live superseder is not walked, and the superseder records both lines. Most useful, most machinery, and it has to decide what a repo *past* the wrong version records.
2. Annotate only: `cmd_status` and the walk list mark a superseded step so the agent walking it knows the correction follows. Cheap, and relies on the agent reading it.
3. Write the limitation into `references/authoring-a-step.md` under the `supersedes:` section, so the next author prices it before choosing that route rather than discovering it afterwards. Cheapest, changes no behaviour, and is honest.

3 is worth doing whichever of the others wins, since the section currently reads as though the mechanism protects repos it does not protect.
