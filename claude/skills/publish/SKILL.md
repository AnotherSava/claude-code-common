---
name: publish
description: >-
  Configure and run PUBLISH — ship a project outward to where its users are. The counterpart to `deploy`, which
  only makes code runnable on this machine. Writes `config/publish.env` and a per-machine `scripts/publish.sh`
  wrapper, then publishes and verifies the live result.
  TRIGGER when: the user explicitly runs /publish or asks to set up publishing for a project.
  DO NOT TRIGGER when: the user says "deploy", "ship", "redeploy" or similar in passing — publishing to production
  is deliberate and must be named; when the task is tagging a version or cutting a GitHub Release (that is
  `release`); or when the project publishes from CI only (see §1).
allowed-tools: Bash(bash ~/.claude/skills/publish/scripts/publish-ssh-compose.sh), Bash(bash scripts/publish.sh), Bash(publish), Bash(git status:*), Bash(git log:*), Bash(git rev-parse:*), Bash(ssh:*), Bash(grep:*), Bash(test:*), Read, Write(config/publish.env), Write(scripts/publish.sh), Edit(~/.gitignore), AskUserQuestion
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

## 2. Write `config/publish.env`

Ask for anything **Publish env** does not already contain — never re-ask for a key that is present. Required:

| Key | Meaning |
|---|---|
| `PUBLISH_TYPE` | `ssh-compose` |
| `SSH_HOST` | `user@host` for the box |
| `REMOTE_REPO` | the checkout on the box, reconciled with a hard reset |
| `COMPOSE_DIR` | directory holding the compose file |
| `APP_CONTAINER` | container name, for the restart-count check |
| `VERIFY_URL` | a real user-facing page — **not** a health endpoint |

Optional: `BUILD_SERVICES` (default `app`), `VERIFY_URL_EXTRA`, `DOPPLER_PROJECT` + `DOPPLER_CONFIG` + `ENV_FILE`,
`VHOST_SRC` + `VHOST_DIR` + `PROXY_STACK` + `PROXY_SERVICE`, `SETTLE_SECONDS` (default 25), `BRANCH` (default
`main`).

Read values from the project rather than asking, where they are discoverable: the compose file gives the service
and container names, the vhost file gives the ingress path, `doppler projects` gives the project name. Ask only
for what genuinely cannot be inferred — above all `SSH_HOST`, which is never in the repo.

`config/publish.env` is **per-machine and gitignored globally**, like `config/deploy.env`. Ensure the global
excludes file carries `config/publish.env`; add it if missing, using the same idempotent append the deploy skill
uses for its own entries.

## 3. Write the wrapper

`scripts/publish.sh` in the repo, a pass-through so the `publish` shell function finds it:

```bash
#!/bin/bash
bash ~/.claude/skills/publish/scripts/publish-ssh-compose.sh "$@"
```

Per-machine and never committed. `~/.gitignore` already lists `scripts/publish.sh` under the per-machine wrappers
header — confirm the line is there rather than adding a duplicate.

## 4. Shell integration

`publish()` delegating through `run_repo_script` is already installed in the shell rc on this machine. Install it
only if **`publish()` in shell rc** reads 0, alongside `run_repo_script` if that is also missing (the `deploy` and
`build` skills install the identical helper — add if absent, never duplicate):

```bash
publish() { run_repo_script scripts/publish.sh "$@"; }
```

The canonical set of these functions is listed in `~/.claude/learnings/shell-environment.md`; keep it in step when
adding one.

## 5. Publish

Run `bash scripts/publish.sh`. If step 3 or 4 wrote anything, say that the shell function needs a Claude Code
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
