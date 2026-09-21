---
created: 2026-09-20 17:59:25
---

# Nothing reports a skill rename breaking its callers in other repos

Renaming a skill directory in this repo silently breaks every repo that shells out to `~/.claude/skills/<name>/scripts/…`. The path is a string, so nothing resolves it until someone runs the code holding it, and no tree reports the break.

Measured case: `documentation` was renamed to `docs-relevance` in de9d4b2 (2026-09-17). Both of tauri-dashboard's capture libs kept resolving the old path and sat broken until ddd912b (2026-09-20) — three days. That repo now gates its own callers with docs/screenshots/check-skill-scripts.py. No other repo has anything equivalent.

The full writeup is claude/learnings/skill-scripts-as-a-dependency.md, committed in 681b962. What it does NOT settle is where the guard belongs, which is this memo.

Two things make the obvious answer wrong:

1. A `claude/conventions/universal/` rule would run in every repo whose gate calls the checker, which is the right reach. But each repo's call shape differs — a Python helper, an inline PowerShell Join-Path, a bash wrapper — so a universal rule carrying a fixed grep pattern restates the reference list instead of reading it out of the source. That is precisely the failure the learning's first design point warns against, and an empty match set would then read as a clean pass.

2. The deploy skill's per-machine `scripts/deploy.sh` wrappers hardcode `bash ~/.claude/skills/deploy/scripts/<TARGET>` and are kept out of git by the global excludes file. No checker in any repo can see them, so renaming `deploy` breaks every repo's shortcut on every machine with nothing able to report it.

Next step: decide whether the guard sits on the rename side (something in this repo that sweeps the sibling checkouts when a skills/ directory is renamed) or the caller side (a universal rule each repo parameterises with its own call shape), and whether the gitignored wrappers get a regeneration step instead of a check. Until then the only protection is the learning's closing section, which an agent has to remember to read.
