---
title: The commit gate runs the conventions checker
scope: repo
---

# The commit gate runs the conventions checker

## What changed

The continuing half of a convention is now a rule under `claude/conventions/rules/`, and
`claude/conventions/check.py` runs the rules a repo's adopted number entitles it to. Nothing invokes
that on its own. Until a repo's `.claude/commit-checks.sh` calls it, the repo can adopt every version
in the set and still have every rule measured exactly once — by the walk, on the day it ran — with
nothing looking again afterwards. The migrations would be done and the enforcement would be nowhere,
which is the half of the design that stops a repo drifting back out of shape between walks.

It also withdraws an answer version 13 used to allow. That version asks what a machine could run here
that would say anything about a change, and a repo with no build, no suite and no linter was entitled
to answer "nothing" and write no file at all. The checker is something a machine can run in every
repo that adopts, so that answer is no longer available: a repo may still have nothing else worth
gating, and it now has this.

## Migrating an existing repo

Add one line to `.claude/commit-checks.sh`, near the top, so a convention violation is reported
before the slower suites run:

```sh
python3 ~/.claude/conventions/check.py .
```

The argument is the repo root, and the script is reached through the installed path rather than a
checkout path, because only the dotfiles repo has `claude/conventions/` inside it — there it is
`python3 claude/conventions/check.py .` instead. Wrap it in whatever this repo's gate uses to label
and buffer a step; if the file has no such helper, the bare line above is enough.

Where `.claude/commit-checks.sh` does not exist, create it. Give it a header saying what it runs, why,
and what a pass does not cover, which is what stops the next reader trusting it for more than it
checks — the dotfiles repo's own file is the worked example.

Then run `bash .claude/commit-checks.sh` and read what it prints. The checker names every rule it
took on and every rule it could not measure; a rule reported `UNMEASURED` is not a pass and is the
thing to settle before moving on.

## When it does not apply

Nowhere this walk reaches, and that is deliberate rather than an omission. A repo that adopts nothing
— a third-party clone, or one carrying an `exempt` record — never gets here at all, because that is
settled before any version is read. Every repo that does adopt takes on rules as its number rises, so
there is no repo for which running the checker is meaningless. A gate that exists but never calls it
is the case this version exists to end, not a condition that excuses it.

## Continuing rule

None — this is a one-time migration, and a rule could not cover it even in principle. A rule
asserting that the gate invokes the checker would itself be run by the checker, so in precisely the
repo where the assertion is false it would never execute. What catches a later removal is the walk's
closing report, which says when this repo's gate does not run `check.py`, and the gate's own output,
which names the rules it took on every time it runs.
