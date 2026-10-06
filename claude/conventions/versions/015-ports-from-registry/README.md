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
`scripts/dev.sh`, and a compose host publish. A survey on 2026-10-05 found one project spanning four files. Two ports were claimed by two projects each, and a `tailscale serve` mapping fronting a dev
server from the port that server had to bind made it unstartable on the second run.

The ports registry now owns every port this machine's projects take, keyed by use case:
`~/.claude/skills/ports/`. A project asks for its number at launch and gets the same one every time.

What that buys is a check a grep can do. With the number resolved at launch, a port literal in a
launch-determining file is either a defect or a number that genuinely cannot move — and the second kind
says so in the registry, as a `pinned` claim. So "does this repo hardcode a port?" is answerable from the
repo's own files, with nothing to compare and no adoption state to keep in sync.

Three kinds of literal stay, and the rule allows each once the registry records it as `pinned`:

- **Fixed by an outside party** — a URL-restricted API key, an OAuth redirect URI registered with a
  provider, a protocol default another tool assumes. travel-map's `8000` is pinned by a Mapbox token
  restriction that takes no wildcards and no port ranges.
- **Compiled in** — a default inside a binary, which no launch-time script can reach. The dashboard's
  `server_port` and `listen_port` live in Rust source.
- **A vendor's default** — PostgreSQL's `5432`, MongoDB's `27017`. The number is typed into connection
  strings by hand and quoted in `.env.example`; making it dynamic churns more than it protects.

Prose is not in scope and never was. A README telling a human which URL to open, an `.env.example`
default, a test asserting a URL, a compose healthcheck on a container-internal port — all of those are
literals no launch-time resolution can replace, and the rule does not look at them.

## Migrating an existing repo

Do this in the repo that is behind, not in the dotfiles repo.

1. **Find what the rule will find.** Run
   `python3 ~/.claude/skills/ports/scripts/ports.py check --repo .` and read every line. It scans only
   the files that decide where a server listens — `package.json` scripts, `scripts/`, compose host
   publishes, a Vite config, `src-tauri/src/config.rs`, `build.gradle.kts` — and names the literal, its
   line and what the registry says about that number. An empty report means the migration is a no-op
   here; record the version and stop.

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

4. **Delete the dead copy.** Remove the `DEV_PORT=` line from `config/deploy.env` if it has one. The
   deploy script reads the registry now. That file is gitignored and per-machine, so this is not part of
   the commit, and the other machine's copy needs the same edit when it gets there.

5. **Check it runs, both ways in.** `bash scripts/deploy.sh` for the deploy path, and `npm run dev` from
   the directory holding the dev script for the hand-run path. Both must come up on the registry's number
   — the second one is the entry point this version exists to fix, since a bare `next dev` with no flag
   and no `PORT` starts on 3000 and drifts upward on a collision. Then re-run step 1; it must report
   nothing.

A project whose server is not started by a Node-capable script — a Gradle task, a Swift test harness, a
shell script with no Node nearby — pins its port in step 2 with that as the reason, and skips step 3.
Nothing here requires inventing a Node dependency a repo does not have.

## When it does not apply

- **No launch-determining file tracked at all.** Step 1 reports nothing because there is nothing to scan:
  no `package.json`, no `scripts/`, no compose file, no Vite or Tauri config, no Gradle build. Evidence
  is `git ls-files` over those paths coming back empty, which the checker already does.
- **Every literal it finds is already a `pinned` claim owned by this repo.** The report is empty and the
  registry carries the reason for each number. A repo of externally-fixed ports is conforming, not
  exempt.
- **The repo takes no port.** Same empty report, reached by having no literal rather than by having
  pinned ones. An absent `config/deploy.env` is not evidence of this on its own — it is per-machine, so
  it says only that this machine has no local deploy configured.

## Continuing rule

`ports-from-registry` — every port literal in a launch-determining file is a `pinned` claim in the ports
registry owned by this repo.
