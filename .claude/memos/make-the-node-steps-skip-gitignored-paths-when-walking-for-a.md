---
created: 2026-09-15 14:39:23
---

# Make the Node steps skip gitignored paths when walking for a package.json

Measured 2026-09-15 by the `/adopt` audit in this repo.

## What it looks like

`conventions.py audit` reports v7 `node-engines-declared` and v9 `package-manager-pin` as needing an answer the step cannot read off the repo, and v8 `engine-strict` reports `1 project manifest(s) read`. All three had been recorded hours earlier the same day with notes saying the opposite — "no package.json outside node_modules/ and the other build and dependency trees this step never descends into — there is no Node project here".

## The cause

One file: `tmp/i-have-adhd/package.json`, a scratch clone sitting in the repo-root `tmp/` that `.gitignore` excludes with `/tmp/`. `git check-ignore -q` agrees it is ignored. The walk never asks.

The 22 manifests under `claude/skills/adopt/steps/fixtures/` are correctly skipped, because `node_manifests.py` already refuses one class of path through `_own_fixtures.prune`. Gitignored paths are simply not in that class.

## Why one fix, not three

All three steps read manifests through `node_manifests.read_all`, so the change has one home.

## The decision to make first

Two candidate rules, and they are not equivalent:

1. **Skip what git ignores** — one `git check-ignore --stdin` pass over the candidate paths. Correct everywhere and for every ignored directory, not just this one. Costs a subprocess; the skill already forks git elsewhere.
2. **Skip `tmp/`** — narrower, and the scratch directory is a documented convention rather than an accident (see `feedback_scratch_lives_in_project_tmp`). Cheaper, and wrong the moment a repo ignores a manifest somewhere else.

The first reads as more right. It is a judgement, not a settled thing.

## One constraint the fix has to clear deliberately

`node_manifests.py` is a shared module beside the steps rather than a step script, so the rule that a shipped step is never behaviourally edited does not obviously bind it. Decide that explicitly instead of by default: a repo already past v7 through v9 will never re-run them, so an edit reaches only repos that have not got there yet — which is exactly the asymmetry `supersedes:` exists for. `references/authoring-a-step.md` has that rule.

## Reach beyond this repo

Every project is told to put scratch in a gitignored `tmp/`, so any clone holding one gets the same false reading — and what gets recorded from it is an `n/a` or a `declined` line about a Node project that does not exist.
