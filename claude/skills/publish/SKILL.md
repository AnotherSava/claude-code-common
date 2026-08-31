---
name: publish
description: >-
  Configure and run PUBLISH — ship a project outward to where its users are. The counterpart to `deploy`, which
  only makes code runnable on this machine. Writes `config/publish.env` and a per-machine `scripts/publish.sh`
  wrapper, then publishes and verifies the live result. Owns the WHOLE configuration path, including what a
  co-tenant on a shared host must obtain from the `landlord` repo before its first publish can work (§2).
  TRIGGER when: the user explicitly runs /publish or asks to set up publishing for a project.
  DO NOT TRIGGER when: the user says "deploy", "ship", "redeploy" or similar in passing — publishing to production
  is deliberate and must be named; when the task is tagging a version or cutting a GitHub Release (that is
  `release`); or when the project publishes from CI only (see §1).
allowed-tools: Bash(bash ~/.claude/skills/publish/scripts/publish-ssh-compose.sh), Bash(bash scripts/publish.sh), Bash(publish), Bash(git status:*), Bash(git log:*), Bash(git rev-parse:*), Bash(git check-attr:*), Bash(git config:*), Bash(ssh:*), Bash(grep:*), Bash(test:*), Read, Write(config/publish.env), Write(scripts/publish.sh), Edit(~/.gitignore), AskUserQuestion
---

# Publish

`deploy` runs it here. `publish` ships it out. `release` tags a version and cuts a GitHub Release. Three verbs,
three entry points, never merged — see `~/.claude/memory/feedback_deploy_publish_separate_verbs.md` for why a
`deploy publish` subcommand was proposed and rejected.

## Context

- Publish env: !`cat config/publish.env 2>/dev/null || echo MISSING`
- Wrapper script exists: !`test -f scripts/publish.sh && echo yes || echo no`
- `publish()` in shell rc: !`grep -c "publish()" ~/.bashrc ~/.zshrc 2>/dev/null | awk -F: '{s+=$2} END {print s+0}'`
- `run_repo_script()` in shell rc: !`grep -c "run_repo_script()" ~/.bashrc ~/.zshrc 2>/dev/null | awk -F: '{s+=$2} END {print s+0}'`
- Compose file: !`ls docker-compose.yml */docker-compose.yml 2>/dev/null | head -1 || echo none`
- Vhost file: !`ls */deploy/*.caddy deploy/*.caddy 2>/dev/null | head -1 || echo none`
- CI publish workflow: !`ls .github/workflows/*publish* .github/workflows/*deploy* 2>/dev/null | head -1 || echo none`
- Git remote: !`git remote get-url origin 2>/dev/null || echo none`
- Crypt filter for `config/publish.env`: !`a=$(git check-attr filter -- config/publish.env 2>/dev/null | grep -c 'filter: crypt'); c=$(git config --get filter.crypt.clean >/dev/null 2>&1 && echo 1 || echo 0); [ "$a" = 1 ] && [ "$c" = 1 ] && echo "READY — attribute set and transcrypt initialised" || echo "NOT READY (attribute=$a initialised=$c) — do NOT write publish.env until both are 1"`

## 1. Decide whether this project should have a local publish path at all

**A project that publishes from CI must not get a `scripts/publish.sh`.** If **CI publish workflow** names a
workflow, read it. When it publishes on push to a branch, stop and say so: the ship *is* the push, and a local
publish path actively causes harm — it uploads the working tree while the deployment is stamped with local `HEAD`,
so uncommitted work goes live under a commit that does not describe it. That exact failure, plus a wrong-config
build that failed only in production, is why one project here deliberately has no publish script. Do not write a
config or a wrapper. Exit.

Also out of scope, each with its own skill: a Chrome extension goes through `/publish-chrome-extension`; a
GitHub Release goes through `/release`. Publish never bumps a version, never creates or pushes a tag, and never
writes release notes.

If the target is not `ssh-compose` and not one of the above, stop and say what is supported rather than
improvising. Adding a target means adding a script under `~/.claude/skills/publish/scripts/`, the way `deploy`
grew from one target to four.

## 2. Co-tenant on a shared host: what the landlord must do first

Skip this when the project owns its own box. It applies when the target fronts several projects behind one
proxy: a separate private repo (`landlord`) owns that host, and four things must exist there before this
project's first publish can succeed. None of them is a tenant's to do, and three a tenant *cannot* do — they
need the host's own credentials, and a tenant holding those is the boundary the whole arrangement exists to
draw. A tenant that finds itself reaching for them has taken a wrong turn, not hit an obstacle.

Ask the landlord session for all four in one message, and wait for confirmation before writing anything below.

| What landlord adds | Why it must come first |
|---|---|
| A grant — `hosts/<host>/tenants/<tenant>.owns`, listing every hostname this project serves | The install gate refuses a vhost claiming a name it was not granted, so the publish fails at the gate having changed nothing. |
| A resolver answer — a line in `hosts/<host>/dns/dnsmasq.conf.template`, then `bin/host-publish` and a rebuild of the DNS container | The rendered file is baked into the image at build time, so nothing short of a rebuild applies it. `host-publish` refuses to run without the host credentials, which is exactly why it is not yours to run. |
| A tailnet split-DNS entry pointing the hostname at the host's tailnet address | Without it the name resolves publicly and never traverses the tailnet. |
| A manifest entry, under `_not_yet_covered` — **not** `targets` | The gate judges arriving targets absolutely, so a target naming a hostname whose certificate has not issued fails the probe and rolls the whole install back. |

**Both DNS halves, or neither.** A resolver line without the split-DNS entry is worse than having neither: the
name resolves publicly, the request arrives from a public address, and any `remote_ip` gate in the vhost locks
the operator out of their own admin routes. Worse, you find out *after* the vhost is installed and while the
certificate clock is running, leaving a half-finished install to unpick. Confirm from a tailnet client before
publishing — `dig +short <hostname>` must return the tailnet address, not a public one.

**The rebuild must name the service.** `host-publish` signs off by printing `docker compose up -d --build` with
no service name. Run verbatim on a shared host, that recreates the proxy and takes 443 from every other tenant.
It is landlord's to run, landlord's defect to fix, and not something a tenant should be running at all.

**The manifest entry is promoted later, in landlord, not here.** Once the first install succeeds and the
certificate issues, the hostname moves from `_not_yet_covered` to `targets` in a separate landlord commit.
Until then the tenant is monitored by nothing — which is the reason the entry exists at all: the host's
self-check asserts that monitored is a subset of granted and not the reverse, so a granted name with no entry
is checked by nothing, silently, and that is the exact shape of failure the manifest exists to catch.

**Run the first identity check by hand.** The gate probes only *arriving* targets, so a tenant sitting in
`_not_yet_covered` has never been asserted end to end — the publish's own identity step will not have covered
it. After the first successful publish, fetch the manifest and run the checker against it once, and read the
report rather than the exit code alone: it prints covered and not-covered separately, and "not covered" is not
the same as fine.

## 3. Write `config/publish.env`

**PRECONDITION — check the crypt filter BEFORE writing, never after.** This file is versioned and encrypted,
so it must be written *into* a working clean filter, not written plaintext and encrypted afterwards. The
write-then-encrypt order leaves plaintext on disk in the window between, and anything that interrupts —
a denied tool call, a crash, the user stopping you — leaves it there indefinitely, which is the exact state
this arrangement removes. Same shape as the script's own `VHOST_GATE` probe: establish the precondition, then
act.

**Crypt filter for `config/publish.env`** in Context is the gate. If it reads `NOT READY`, stop and set it up
before writing anything:

- `attribute=0` — add to the repo's `.gitattributes`, then re-check:
  ```
  config/publish.env filter=crypt diff=crypt merge=crypt
  ```
  Mark it by **path**, not by renaming to `*.secret.*`: the name is part of an interface here, not a label —
  `config/publish.env` is the literal path the publish script reads, nothing in the repo references the name,
  so a rename breaks every publish on every machine and grepping would not catch it. Scope it to this one path
  rather than `*.env`, too: a host's deliberately-committed plaintext `host.env` and a rendered file full of
  secret values share that suffix and need opposite handling, so the suffix cannot carry the decision.

  **Do not add `-text`** — transcrypt stores base64, which is text, and marking it binary churns the blob on
  every Windows↔macOS round trip. The `/transcrypt` skill carries the full reasoning; it applies to a
  path-marked entry exactly as it does to the `*.secret.*` pattern it is written against.
- `initialised=0` — run `/transcrypt`, which uses the shared Doppler key. Never generate a new passphrase.

Then verify what git would actually store, using the procedure in
`~/.claude/learnings/transcrypt-verify-before-commit.md` — in particular, do **not** `eval` the filter from
`git config`: the `%f` placeholder never expands, the output is empty, and grepping empty output for your
secret reports "clean" while proving nothing.

Ask for anything **Publish env** does not already contain — never re-ask for a key that is present. Required:

| Key | Meaning |
|---|---|
| `PUBLISH_TYPE` | `ssh-compose` |
| `SSH_HOST` | `user@host` for the box |
| `REMOTE_REPO` | the checkout on the box, reconciled with a hard reset |
| `COMPOSE_DIR` | directory holding the compose file |
| `APP_CONTAINER` | container name, for the restart-count check |
| `VERIFY_URL` | a real user-facing page — **not** a health endpoint |

Optional: `BUILD_SERVICES` (default `app`), `VERIFY_URL_EXTRA`, `DOPPLER_PROJECT` + `DOPPLER_CONFIG` +
`ENV_FILE`, `VHOST_SRC` + `VHOST_DIR` + `PROXY_STACK` + `PROXY_SERVICE`, `SETTLE_SECONDS` (default 25),
`BRANCH` (default `main`). Also `IDENTITY_CHECK` and `HOST_MANIFEST`, both of which a co-tenant should leave
unset — see below for why writing one is a regression rather than extra care.

Two of those decide whether the publish can see the failures a 200 hides:

- **`IDENTITY_CHECK`** — a command run locally after the URL checks; a non-zero exit fails the publish.
  `VERIFY_URL` proves *something* answers; only this proves the answer is **yours**. A name collision between
  two projects can point a hostname at a neighbour's app, which returns 200 just as healthily — one storefront
  served the wrong application for 41 hours with every other check green.

  **Leave it unset. The host supplies it.** The key is documented here because the script names it, not because
  you should write one: the script probes the host for an executable at `HOST_MANIFEST` (default
  `/opt/landlord/bin/host-manifest`) and, finding one, fetches the manifest over the ssh connection it already
  holds and runs the checker itself. That checker is a stdlib-only script shipped beside this skill at
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/identity-check.py`, taking a per-host manifest as its argument.
  Set the key only if this project genuinely needs a *different* check from every other tenant on its box — and
  the script will say so when you do.

  **What is not neutral is having neither.** On a box showing any shared-proxy signal, a publish with no
  configured value *and* no host default stamps the result `PUBLISH OK — NOT IDENTITY-VERIFIED` and says so
  loudly, because one project published for weeks with no assertion that its hostname served its own app and
  nothing ever mentioned it. Inheriting the host's default is not that state — and writing your own copy is not
  an improvement on it.

  **The manifest is fetched, never stored.** It inventories a box's hostnames plus the marker each site emits —
  what an impersonation would have to reproduce to pass this very check — so it lives once, in the private repo
  that owns the host, and every publish pulls it. Stored copies were tried twice and drifted both times.

  **The `gh api` form is retired. If you find it written down, it is stale.** The value used to be ~700
  characters of shell copied byte-identically into every tenant's config — a single source of logic smeared
  across repos that cannot see each other, where a fix to one silently missed the rest. It fetched the manifest
  from the host repo's default branch with `gh api`, so the check asserted against what was *committed* rather
  than what the box was *serving*; it needed an authenticated `gh` on every publishing machine; and being an
  unquoted `$(…)`, it turned an accidental `source config/publish.env` into a live network call whose failure
  read exactly like a dead token. Two places in the publish script still send operators to "the publish skill
  for the portable form" — this paragraph is what they should find. The portable form is *no form*.
- **`VHOST_DIR`** — set it only in *co-tenant* shape, where this repo owns one vhost inside somebody else's proxy
  and the file has to be installed on the box. Leave it unset when this repo **owns the proxy**: the config is
  already in the checkout the reconcile reset, so `VHOST_SRC` alone decides whether to force-recreate. Setting it
  in that case makes the publish copy a file onto itself.

  **`VHOST_SRC` also decides whether the vhost gets linted at all, which is not obvious from its name.** The
  authoring-time hook checks tenancy rules only against the file this key names; a repo without a
  `config/publish.env`, or with the key absent, gets `clean (N file(s) checked)` and exit 0 having applied no
  tenancy rule to its vhost. Measured on a live tenant that had `config/deploy.env` and no publish config. So a
  new co-tenant is unlinted for exactly as long as it takes to finish this step — set `VHOST_SRC` early, and do
  not read a green hook on a half-configured repo as evidence of anything.

Read values from the project rather than asking, where they are discoverable: the compose file gives the service
and container names, the vhost file gives the ingress path, `doppler projects` gives the project name. Ask only
for what genuinely cannot be inferred — above all `SSH_HOST`, which is never in the repo.

`config/publish.env` is **committed, encrypted**, and is not per-machine — unlike `config/deploy.env`, which
stays gitignored because it genuinely differs per machine. Do **not** add `config/publish.env` to the global
excludes file: that rule was removed on 2026-08-28 deliberately, because two machines each keeping their own
uncommitted copy is drift with no mechanism to detect it, and drift in this file is a publish that behaves
differently depending on where it is run from. One committed copy, encrypted at rest in git, plaintext in the
working tree; a `git pull` is what carries it to the other machine.

A pre-commit hook refuses to commit this path unless it is marked `filter=crypt`, so the failure mode of
skipping this section's precondition is a blocked commit rather than a plaintext config on a remote.

**⚠️ It must never be `source`d, and every copy should carry a header comment saying so.** It looks like an env
file and is not one: the script reads it with `grep`+`cut`, so values are deliberately unquoted *commands*.
Sourcing runs them.

The case that is always present: a multi-word value like `BUILD_SERVICES=app migrate` is a shell **prefix
assignment**, so sourcing executes `migrate` as a command and scopes the assignment to that command alone.
The variable keeps whatever it held before — unset stays unset, a stale value stays stale — so the value you
believe you just loaded is not loaded, and the only hint is a `command not found` for a binary that is on no
PATH. Any value carrying an unquoted `$(…)` is
worse — sourcing fires it at assignment time and stores the output, so the variable holds a *result* where a
command belongs, and the eventual failure looks nothing like its cause. That is not hypothetical: it cost one
wrong diagnosis, an operator chasing a credential that was fine. Values ending in `exit` will also close an
interactive shell outright.

To inspect a value, print it rather than execute it — this is the same `grep`+`cut` the script itself uses,
which is why the script is safe and your shell is not:

```
grep '^BUILD_SERVICES=' config/publish.env | cut -d= -f2-
```

## 4. Write the wrapper

`scripts/publish.sh` in the repo, a pass-through so the `publish` shell function finds it:

```bash
#!/bin/bash
bash ~/.claude/skills/publish/scripts/publish-ssh-compose.sh "$@"
```

Per-machine and never committed. `~/.gitignore` already lists `scripts/publish.sh` under the per-machine wrappers
header — confirm the line is there rather than adding a duplicate.

## 5. Shell integration

`publish()` delegating through `run_repo_script` is already installed in the shell rc on this machine. Install it
only if **`publish()` in shell rc** reads 0, alongside `run_repo_script` if that is also missing (the `deploy` and
`build` skills install the identical helper — add if absent, never duplicate):

```bash
publish() { run_repo_script scripts/publish.sh "$@"; }
```

The canonical set of these functions is listed in `~/.claude/learnings/shell-environment.md`; keep it in step when
adding one.

## 6. Publish

Run `bash scripts/publish.sh`. If step 4 or 5 wrote anything, say that the shell function needs a Claude Code
restart before `! publish` resolves — and use the direct path meanwhile.

The script's own steps are documented in its header. What matters here is what it refuses:

- **Uncommitted or unpushed work stops it.** The box pulls from the remote; there must be a commit to pull.
- **The build is detached and polled**, because a compose build routinely outlives the tool timeout.
- **The proxy is only recreated when the vhost actually changed** — a bind-mounted config file keeps its old inode,
  so a reload reports "config is unchanged" and the new vhost silently never gets a certificate; recreating is the
  only reliable fix, and it briefly interrupts every site that proxy fronts.
- **Success is proved by observing the target.** A real page must return 200 *and* the container's restart count
  must not climb during verification. A health probe is not enough: one has passed while every database-backed
  page returned 502, and a crash-looping container answers 200 between restarts.

Report the result plainly, including a failure — never describe a publish as done on the strength of a green
build.

## Authorization

Publishing is a deliberate, consequential act. Invoke this skill only when the user explicitly runs `/publish` or
names publishing; never infer it from "deploy", "ship" or "redeploy". For a production target, a bare "go" in
reply to something else does not clear the bar — the user must name what is being published.

## Out of scope

- Do NOT create or push tags, bump versions, or write release notes — that is `release`.
- Do NOT publish a working tree, or anything not on the remote.
- Do NOT write a wrapper for a project that publishes from CI.
- Do NOT do first-time server provisioning (users, Docker, the proxy stack, DNS) — this skill ships an app to a box
  that is already serving one.
