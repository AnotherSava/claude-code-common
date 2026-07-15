---
name: Deploy via the script, not the deploy skill
description: When a project's deploy is already configured, run the deploy script directly instead of invoking the deploy Skill
type: feedback
---

When you need to deploy and the project is already set up for it (a `scripts/deploy.sh` wrapper or the `deploy` shell function exists), run it directly via Bash — do not invoke the deploy Skill. Both `deploy` and `bash scripts/deploy.sh` now work from **any** working directory: the `deploy` shell function walks up to the repo root via `run_repo_script`, and the underlying `deploy-*.sh` target scripts independently resolve the repo root (the nearest ancestor holding `config/deploy.env`, via the shared `_repo-dir.sh` helper). Either is fine; `deploy` is just shorter.

**History (fixed 2026-07-12):** the underlying scripts used to set `REPO_DIR="$(pwd)"`, so calling `bash scripts/deploy.sh` (or an underlying `deploy-*.sh`) directly from a subdir like `web/` read a nonexistent `web/config/deploy.env` and silently fell back to defaults — wrong port/dir with no error (a dev server meant for port 3939 came up on 3000, and since Next 16 allows only one dev server per project dir, that stray same-project instance blocked the real 3939 server — a different project's server on 3000 would NOT conflict; the lock is per-project, not machine-wide). Hardened by adding `resolve_repo_dir` in `~/.claude/skills/deploy/scripts/_repo-dir.sh`, sourced by all five target scripts.

**Why:** The deploy Skill re-runs its context probe and setup decision tree on every invocation. That ceremony only matters the first time, to create the wrapper / `config/deploy.env`. Once a project is configured, invoking the Skill just adds overhead and produces the same result as running the script. Observed 2026-05-30: I called the deploy Skill on an already-configured Tauri project, and it even emitted a "restart Claude Code before `! deploy` works" reminder that didn't apply (nothing was newly written to `.bashrc`).

**How to apply:** Reserve the deploy Skill for first-time setup only — when no `scripts/deploy.sh` / `deploy` function / `config/deploy.env` exists yet and the project needs wiring up. In every other case, deploy by running the script directly. Complements the project-level "run deploy directly, don't hand it back to the user" feedback — that one says *don't ask the user to run it*; this one says *don't route through the Skill to do it*.
