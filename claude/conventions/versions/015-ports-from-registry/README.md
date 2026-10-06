---
title: A project's port comes from the registry at launch, not from a literal in its dev script
rules: ports-from-registry
optional: forks
---

## What changed

A port written into a dev script is a copy of a number something else also holds, and it is the copy the
process actually reads. Nothing reconciled the two. Before this, the deploy skill chose a dev port by
regexing a `package.json` for a `-p` flag and falling back to `3000` — which is printlab's dev port — and
the number then settled into `config/deploy.env`, a `package.json` script, sometimes a project
`scripts/dev.sh`, and a compose host publish. A survey on 2026-10-05 found one project spanning four
files. Two ports were claimed by two projects each, and a `tailscale serve` mapping fronting a dev
server from the port that server had to bind made it unstartable on the second run.

The ports registry now owns every port this machine's projects take, keyed by use case:
`~/.claude/skills/ports/`. A project asks for its number at launch and gets the same one every time.

What that buys is a check that reads the repo instead of reconciling two records. With the number resolved
at launch, a port literal in a launch-determining file is either a defect or a number that genuinely cannot
move — and the second kind says so in the registry, as a `pinned` claim.

An absent literal answers only half of it, because a repo that resolves nothing holds no literal either. The
other half asks the registry which ports it assigns this repo and requires a launch-determining file here
that asks for each — the same files the literal scan reads, so a README or CLAUDE.md sentence naming the
tool never passes for a resolver; the registry is where that set is knowable, since the repo's own files
cannot say which ports it ought to have. Neither half keeps an adoption state in sync.

Four kinds of literal stay, and the rule allows each once the registry records it as `pinned`:

- **Fixed by an outside party** — a URL-restricted API key, an OAuth redirect URI registered with a
  provider, a protocol default another tool assumes. travel-map's `8000` is pinned by a Mapbox token
  restriction that takes no wildcards and no port ranges.
- **Compiled in** — a default inside a binary, which no launch-time script can reach. The dashboard's
  `server_port` and `listen_port` live in Rust source.
- **A vendor's default** — PostgreSQL's `5432`, MongoDB's `27017`. The number is typed into connection
  strings by hand and quoted in `.env.example`; making it dynamic churns more than it protects.
- **No launch path to resolve it at** — a number in a recipe a person runs by hand, or one two places
  must carry identically with nothing starting either. The dotfiles repo's own ports are mostly this:
  a throwaway Caddy started at a prompt, a consent URL and its token exchange in one shell script.

Prose is not in scope and never was. A README telling a human which URL to open, an `.env.example`
default, a test asserting a URL, a compose healthcheck on a container-internal port — all of those are
literals no launch-time resolution can replace, and the rule does not look at them.

## Migrating an existing repo

Do this in the repo that is behind, not in the dotfiles repo.

1. **Find what the rule will find.** Run
   `python3 ~/.claude/skills/ports/scripts/ports.py check --repo .` and read every line. It reports two
   different things, and an empty report means both came back empty:

   - **A port literal** in a file that decides where a server listens — `package.json` scripts,
     `scripts/`, compose host publishes, a Vite config, `src-tauri/src/config.rs`, `build.gradle.kts`
     — named with its line and what the registry says about that number.
   - **A port the registry assigns this repo that no launch-determining file here asks for** — the
     same files as above, so a sentence in a README or `CLAUDE.md` naming the tool is not one. An
     absent literal is not resolution: a dev script with no `-p` and no resolver takes its
     framework's default and drifts upward on a collision, which is a worse failure than the literal
     because nothing names the port at all. Measured 2026-10-05: printlab and what-is-next were both
     in exactly that state.

   Only when it reports neither is the migration a no-op here, and then record the version and stop.

2. **Decide each literal: resolve it, or pin it.** A port the project's own server listens on and that
   nothing outside the machine depends on gets resolved at launch (step 3). A port in one of the three
   classes above gets recorded instead:

   ```bash
   python3 ~/.claude/skills/ports/scripts/ports.py allocate \
     --use-case <repo>-<what-listens> --owner <repo> --port <n> \
     --pinned "<why this number and no other>" --notes "<what listens, and how it starts>"
   ```

   The `--pinned` text is what a reader gets instead of the session this decision came from. "Mapbox
   restrictions take no wildcards or port ranges" is a reason; "it has always been 8000" is not — if that
   is the honest answer, the port is resolvable and belongs in step 3.

3. **Resolve the rest at launch.** Copy `dev.mjs` from this version's folder into the repo's `scripts/`,
   set its `USE_CASE` and `OWNER` to this repo's, then rewrite the dev and start scripts to call it with
   the port literal removed:

   ```jsonc
   // before
   "dev":   "doppler run -- next dev -p 3940",
   "start": "doppler run -- next start -p 3940",
   // after
   "dev":   "doppler run -- node ../scripts/dev.mjs next dev",
   "start": "doppler run -- node ../scripts/dev.mjs next start",
   ```

   Mind the relative path: a `package.json` in `web/` reaches a repo-root `scripts/` as `../scripts/`.
   Use the use case the registry already holds for this repo — `ports.py list` shows it — rather than
   inventing a new slug, or the server comes up on a freshly allocated port while everything else still
   expects the old one.

4. **Delete the dead copies — both of them.** Remove the `DEV_PORT=` line from `config/deploy.env`,
   which the deploy script no longer reads, **and any `-p <n>` left inside `DEV_CMD`**. Dropping the
   first alone leaves the duplicate one line lower, where it overrides the `PORT` the script exports and
   so wins silently; `ports.py check --repo .` reports each separately. Measured 2026-10-05 in
   what-is-next: with both gone and `DEV_CMD=npm run dev`, the exported `PORT` reaches `next dev` through
   `doppler run` and the server still comes up on the registry's number. That file is gitignored and
   per-machine, so this is not part of the commit, and the other machine's copy needs the same edit.

5. **Check it runs, both ways in.** `bash scripts/deploy.sh` for the deploy path, and `npm run dev` from
   the directory holding the dev script for the hand-run path. Both must come up on the registry's number
   — the second one is the entry point this version exists to fix, since a bare `next dev` with no flag
   and no `PORT` starts on 3000 and drifts upward on a collision. Then `git add` the new `scripts/dev.mjs`
   and re-run step 1; it must report nothing. Staging comes first because the check reads tracked files,
   so while the script is untracked it still reports the registry's port as one no file here asks for, and
   the migration reads as having failed.

A project whose server is not started by a Node-capable script — a Gradle task, a Swift test harness, a
shell script with no Node nearby — pins its port in step 2 with that as the reason, and skips step 3.
Nothing here requires inventing a Node dependency a repo does not have.

## When it does not apply

- **The registry assigns this repo no port.** Then there is nothing for a literal to copy and nothing
  for a resolver to fetch, and step 1 reports neither half. Evidence is `ports.py list` carrying no
  `machine`-scope claim whose owner is this repo — read off the registry, not inferred from the repo's
  own files. `bga-assistant` is this case and conforming: its `dev` script is `vite build --watch`, a
  build watcher that binds nothing.
- **Every port it assigns this repo is a `pinned` claim.** The report is empty and the registry carries
  the reason each number cannot move. A repo of externally-fixed ports is conforming, not exempt — the
  dotfiles repo itself is this case, its own ports being a module constant, Chrome's DevTools default,
  and literals written into scripts and recipes a person runs by hand.
- **No launch-determining file tracked at all,** with no claim either: nothing to scan and nothing
  owed. An absent `config/deploy.env` is not evidence of any of these on its own — it is per-machine,
  so it says only that this machine has no local deploy configured.

## Continuing rule

`ports-from-registry` — every port literal in a launch-determining file is a `pinned` claim in the ports
registry owned by this repo, and every unpinned port the registry assigns this repo is asked for by a
launch-determining file here.
