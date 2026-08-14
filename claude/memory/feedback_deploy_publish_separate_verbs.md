---
name: Keep deploy and publish as separate verbs
description: `deploy` makes code runnable here, `publish` ships it outward — separate scripts and shell functions, never a `deploy publish` subcommand
type: feedback
---
`deploy` and `publish` are two different verbs and get two different entry points. `deploy` makes the latest code runnable **on this machine** (local dev server, local install). `publish` ships it **outward** (Cloudflare Pages upload, store submission, registry release). Each gets its own `scripts/<verb>.sh` wrapper and its own shell function delegating through `run_repo_script`. Do not add a mode flag or subcommand — `deploy publish` is the wrong shape.

**Why:** folding the outward ship into `deploy` puts a production release one argument away from a local preview, and the two need different credentials and different Doppler configs — exactly the mix-up that once baked a localhost-only Mapbox token into a production build. Separate verbs also keep the mental model clean: nothing outward-facing can happen from the command you run dozens of times a day. (Established 2026-08-09 after `deploy publish` was proposed and rejected.)

**How to apply:**
- Wire whichever verbs the project actually has. A project with no local publish path should have **no** `scripts/publish.sh` at all rather than a convenience one — check the project's own memory/docs before adding it, since CI-only publishing is a deliberate design in some repos.
- Both wrappers are per-machine and gitignored globally, alongside `config/deploy.env`.
- `release` (tag → CI → GitHub Release) is a third verb; don't merge it into either.
- See [[feedback_deploy_script_not_skill]] and [[feedback_user_run_commands_bang_prefix]].
