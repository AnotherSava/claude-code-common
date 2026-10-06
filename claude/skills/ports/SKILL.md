---
name: ports
description: >-
  Hand out and record the TCP ports this machine's projects take, from one committed registry keyed by use case —
  so a port is never guessed, never silently shared, and always has an owner on record.
  TRIGGER when: a project needs a port it does not have yet (a dev server, a sidecar, a local database, a
  one-off probe server, a tailnet front port); a port collision or an unexplained EADDRINUSE is being
  diagnosed; a port's owner is in question ("what is on 3942?", "can I use 8000?"); a port is being retired;
  or the registry needs checking against this machine.
  DO NOT TRIGGER when: the port is inside a Docker network (a container namespace is not shared — record it
  once with `--scope container` and move on), or the task is publishing a server on the tailnet, which is
  `shared/tailnet_publish.py` and only needs this skill for the front port number.
allowed-tools: Bash, Read, Edit, Glob, Grep
---

# Allocating a port

One registry, `registry.json` beside this file, records every port this machine's projects take, keyed by
use case. `scripts/ports.py` is the only writer. Read its module docstring before changing it — it carries
the scope model and why liveness is not an oracle in either direction.

**Never choose a port by reading a config file, grepping for a free-looking number, or defaulting to 3000.**
That is what produced the collisions this registry exists to end, 3000 among them — it is printlab's dev port and the deploy script's own fallback.

## Assigning a port to a new use case

Run this and use the number it prints. It is idempotent on the use case, so a script may call it on every
run; it writes only the first time.

```bash
python3 ~/.claude/skills/ports/scripts/ports.py allocate \
  --use-case <slug> --owner <repo-or-app> --notes "<why this number>"
```

- `--use-case` is the registry's key: lowercase words joined by single hyphens, naming the *thing that
  listens* rather than the project — `tripit-booking-extract`, not `tripit-port-2`. One project with two
  listeners has two use cases.
- `--notes` is what the next reader gets instead of the session this came from. Say what listens, how it is
  started, and anything that makes the number hard to change.
- `--port N` for a number fixed outside this machine. Required for `--scope remote` and `--scope container`,
  which name ports this machine does not allocate.
- `--pinned "<why>"` when the number cannot be changed — an OAuth redirect URI registered with a provider, a
  URL-restricted API key, a protocol default something else assumes. Required for a port in the WHATWG
  blocked set, below 1024, or in the ephemeral range.
- `--front-for N` when the port is a `tailscale serve` front for a local origin port.

`allocate` steps over any pool port that is claimed, unusable, or **live on this machine right now**, and
says on stderr what it stepped over. A live holder nothing claims is a finding: record it before moving on.

**The registry is committed, so an allocation leaves an uncommitted change in the dotfiles repo.** When the
allocation happened while working in another project, report that diff to the session that owns the dotfiles
repo (the `peer` skill) and leave the commit to it.

## Answering "what is on port N?"

```bash
python3 ~/.claude/skills/ports/scripts/ports.py list              # every claim
python3 ~/.claude/skills/ports/scripts/ports.py get <slug>        # one use case's port
python3 ~/.claude/skills/shared/port_probe.py verdict <port>      # what holds it right now
```

The probe is the second half of the answer and it is the half that finds the holder no process listing
shows. A `tailscale serve` mapping's listener lives in a root-owned system extension, so an unprivileged
`lsof` prints nothing about a port that cannot be bound — which is the shape of every "EADDRINUSE but the
port is free" report. `verdict` tries the bind as well as the listing, and names the mapping when that is
what holds it.

## Retiring a port

```bash
python3 ~/.claude/skills/ports/scripts/ports.py release <slug>
```

Only an `assigned` claim can be released. A `reserved` one records something this machine does not control —
the OS, a vendor default, another host — and releasing it would hand the number to something else.

## Checking the registry

```bash
python3 ~/.claude/skills/ports/scripts/ports.py check                  # the registry as a document
python3 ~/.claude/skills/ports/scripts/ports.py check --live           # ...and what this machine takes that it does not record
python3 ~/.claude/skills/ports/scripts/ports.py check --repo <path>    # ...and whether one repo gets every port it owns from the registry
```

Exit 0 clean, 1 problems found. `--repo` reports two things, and the second is why the first is worth
anything:

- **A port literal in a launch-determining file** — `package.json` scripts, `scripts/`, a compose host
  publish, a Vite config, `src-tauri/src/config.rs`, `build.gradle.kts` — which is a second copy of a
  number the registry owns, and the copy the process reads. Allowed once the registry records it as
  `pinned`: a number fixed by an outside party, a default compiled into a binary, a vendor's own port.
- **An unpinned port the registry assigns this repo that no tracked file asks for.** An absent literal
  proves nothing on its own: a dev script with no `-p` and no resolver takes its framework's default and
  drifts upward on a collision, which is worse, because then no file names the port at all. Measured
  2026-10-05, printlab and what-is-next were both in that state while reporting zero literals. A claim
  carrying `front_for` is exempt, since the deploy script allocates a tailnet front port at publish time
  and the repo never names it.

Prose is deliberately out of scope. A README telling a human which URL to open, an `.env.example` default,
a test asserting a URL, a compose healthcheck on a container-internal port — none can be resolved at launch
and all are correct to leave. Measured 2026-10-05: ten launch-path literals across the fleet against
134 in prose, examples and tests, so a scan that read everything would bury its own findings.

A `--live` notice never changes the exit status, and nor does the one about a `DEV_PORT` line still sitting
in a `config/deploy.env`: the deploy script reads the registry now, so that line is dead rather than wrong.

`check` runs in this repo's commit gate. In a project repo the same scan runs as the convention rule
`ports-from-registry`, which version 015 introduces — so a repo that has adopted it is checked at every
commit without wiring anything, and one that has not is unchecked rather than clean.

## How a project gets its port at launch

The port is resolved when the server starts, so no file in the project carries the number. Two callers ask
the registry for the same use case and arrive at the same answer:

- `deploy-dev-server.sh` resolves `<repo>-dev-server`, exports `PORT`, kills whatever holds that port, and
  health-checks it. Nothing in `config/deploy.env` names a port any more.
- The project's own `scripts/dev.mjs` resolves it for a hand-run `npm run dev`, which is the entry point a
  launcher-only design leaves broken: a bare `next dev` with no flag and no `PORT` starts on 3000 and
  drifts upward on a collision. That shim is a committed per-repo file loading `scripts/dev-port.mjs` from
  this skill, so a fix here reaches every project. Version 015's folder holds the template.

Next and Vite both read `PORT`. Next classifies an env-supplied port as source `env` rather than `default`,
which keeps its retry path off — so the server binds the registry's number or exits, rather than drifting.

Before changing an *assigned* port, still grep the owning repo for it: prose, `.env.example` files and
tests quote the number even when no launch path does, and they go stale silently.

## The tailnet front port

A dev server reached over the tailnet needs **two** numbers: the port it binds, and the port
`tailscale serve` fronts it on. They cannot be the same number for a server that binds the wildcard address
— the mapping takes the wildcard and tailnet addresses and leaves only loopback free, so the server starts
once and then cannot rebind its own port, while every process listing shows that port free.

`deploy-dev-server.sh` does this for a `dev-server` deploy already: it allocates `<repo>-dev-tailnet` on every
run and publishes `publish-port <front> --target <DEV_PORT>`. For a server started any other way, allocate a
front port the same way rather than passing one number to `publish-port`, which refuses a same-number publish
over a wildcard-bound origin and tells you so.

A project whose origin is pinned to `localhost` — a URL-restricted API key, an OAuth redirect, a CORS
allowlist — wants no front port at all. It sets `DEV_TAILNET=no` in `config/deploy.env` and keeps the
`localhost` URL.

The measured mechanics are in `~/.claude/learnings/tailscale-serve-port-ownership.md`.
