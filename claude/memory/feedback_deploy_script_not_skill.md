---
name: Deploy via the script, not the deploy skill
description: When a project's deploy is already configured, run the deploy script directly instead of invoking the deploy Skill
type: feedback
---

When you need to deploy and the project is already set up for it (a `scripts/deploy.sh` wrapper or the `deploy` shell function exists), run the script directly via Bash — `bash scripts/deploy.sh`, or the underlying `~/.claude/skills/deploy/scripts/deploy-*.sh`. Do not invoke the deploy Skill.

**Why:** The deploy Skill re-runs its context probe and setup decision tree on every invocation. That ceremony only matters the first time, to create the wrapper / `config/deploy.env`. Once a project is configured, invoking the Skill just adds overhead and produces the same result as running the script. Observed 2026-05-30: I called the deploy Skill on an already-configured Tauri project, and it even emitted a "restart Claude Code before `! deploy` works" reminder that didn't apply (nothing was newly written to `.bashrc`).

**How to apply:** Reserve the deploy Skill for first-time setup only — when no `scripts/deploy.sh` / `deploy` function / `config/deploy.env` exists yet and the project needs wiring up. In every other case, deploy by running the script directly. Complements the project-level "run deploy directly, don't hand it back to the user" feedback — that one says *don't ask the user to run it*; this one says *don't route through the Skill to do it*.
