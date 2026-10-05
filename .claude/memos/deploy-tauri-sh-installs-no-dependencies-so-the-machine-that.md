---
created: 2026-10-04 23:18:21
---

# deploy-tauri.sh installs no dependencies, so the machine that pulls a lockfile change gets a failing build

Decide how `claude/skills/deploy/scripts/deploy-tauri.sh` should install dependencies before building, and add it.

The gap, verified 2026-10-04 by reading the script: its five steps are `Step 1: Stopping running app`, `Step 2: Building Tauri Release` (`npm run tauri -- build`), `Step 3: Deploying to install directory`, `Step 4: Launching app`, `Step 5: Verifying app started`. A grep for `npm ci`, `npm install`, `pnpm`, `yarn` and `corepack` across the whole file returns nothing. So the build runs against whatever `node_modules` happens to hold.

Why it bites rather than being theoretical: two machines share one lockfile, and the failure lands on whoever pulls rather than on whoever pushed. Reported by the tauri-dashboard session the same day — a commit moved `@tauri-apps/api` to 2.12.1, the Windows box pulled it, and `tauri build` refused the 2.11/2.12 mismatch until `npm ci` was run by hand. The pushing machine's own deploy had worked only because `node_modules` had been updated hours earlier for unrelated reasons, which is luck rather than design.

Reach: the script is in this repo and symlinked to `~/.claude/`, so it is the deploy path for every Tauri project on both machines. That is what makes the choice worth deciding rather than patching in passing.

The three options and what each costs:

- `npm ci` — the correct instrument for a lockfile-driven install, and the only one that guarantees the tree matches the lock. It deletes `node_modules` first, so every deploy pays a full reinstall even when nothing changed.
- `npm install` — cheap when already in sync, but it can leave the tree disagreeing with the lock, which is the class of silent drift the `packageManager` pin exists to stop.
- Install only when `package-lock.json` is newer than `node_modules` — cheap, and covers exactly the case that bites. Needs care about what `node_modules`'s own mtime means after a partial install, and note that an mtime comparison is the instrument `learnings/git-dating-a-file-from-history.md` warns about for a different question; here it is a staleness check rather than an authorship claim, which is the legitimate use.

Whichever is chosen, the step belongs before `Step 2` and should fail the deploy loudly rather than warning, since a build against a stale tree is the thing being prevented.
