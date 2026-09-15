---
version: 12
slug: cotenant-service-names
title: Compose services carry the project's name
scope: repo
---

# Compose services carry the project's name

Docker compose publishes a *service's* key as a DNS alias on every network that service
joins, shared ones included, and `container_name:` adds an alias rather than replacing it.
So two projects that each call a service `app` both answer to `app` on the bridge they
share, and the proxy dials whichever the daemon hands back — walked in sandbox endpoint
order, which nobody controls. In August 2026 that put a commercial storefront on a
neighbour's application for 41 hours, at HTTP 200, with healthy containers, a valid config
and every uptime check green throughout. The mechanics, and the checkers already written
against them, are in `learnings/docker-compose-shared-host-co-tenancy.md`.

The shape this asks for is one name per thing: a service key that carries its project's
name, a `container_name` equal to it, and a vhost basename no neighbour would also pick.

**This step detects and never edits.** A compose service name is dialled from `depends_on`,
from another service's environment, from the vhost's `reverse_proxy` upstream, from
`BUILD_SERVICES` and `APP_CONTAINER` in an encrypted `config/publish.env`, and from the
derived container name a proxy holds when no `container_name` is set. A rename that misses
one of those does not error: it serves the wrong thing behind an HTTP 200, which is the
failure this convention exists to prevent. So the script finds the deviation, names it, and
prints the references it can see; the edit is a human's, and `verify` is what records it.

## Applies when

Never — probe cannot return 0, so `/adopt` stops at the question below rather than reaching
`apply`. This step's `apply` still runs by hand: it exits 3 without writing anything,
printing each finding together with the references in this repo the rename has to reach. Run
it before making the edit. A repo that deviates is reported under `Cannot tell` below, and
`/adopt` puts the finding to the user rather than changing a compose file behind them.

## Does not apply when

The repo holds no compose file, no `*.caddy` vhost and no `config/publish.env`. Those three
absences together are positive evidence that this repo deploys nothing to the shared box
today, so it claims no name in a namespace another project writes to. Ten of the fleet's
repos answered this way when this step was written. It is a fact that expires: `audit`
re-runs probe for every `n/a`
line, so the first of them to become a tenant surfaces as a finding rather than a silence.

## Cannot tell

A service key inside the generic set, a key that does not carry its compose project's name,
a key with no `container_name` or one that differs from it, or a `*.caddy` basename inside
the generic set. Each finding names the file, the line, the name it should carry, and the
rule it breaks; running the step's apply adds the references in this repo that the rename
has to reach.

The generic set is the one `scripts/ingress-lint.py` already refuses at commit time,
imported rather than copied so the two cannot disagree about what generic means, plus
`mongo` and `migrate` — two names the fleet's own compose files use and that list does not
carry. When that import fails the step says so and refuses to judge, rather than falling
back to a second copy of the list.

Three more states are a question rather than an answer:

- **A compose file with no top-level `name:`** — the compose project name is then derived
  from whatever directory the stack is brought up in, so the prefix every service should
  carry has no stable value to check against. Add a `name:` naming the project and re-run,
  or record `declined` if the stack is deliberately brought up under varying names.
- **Compose files with no service key in any of them**, which leaves nothing for the
  convention to be true or false about. Record `n/a` if the file is a fragment or an
  override that only ever extends another stack.
- **A compose file that cannot be opened at all.** Reported as the question, never folded
  into "no compose file here", which would turn an unreadable tenant into a repo that
  deploys nothing. Unlock or repair the file and re-run.

A dev-only compose file is read like any other, and a generic key in one is named. That is
deliberate: one tenant here is the measured case where "it is not on the shared bridge
today" was the defence, while the host's own compose file joins that tenant's default
network to reach exactly those services. A repo that judges its dev stack out of scope records `declined` with that
reason, which is a decision in the record rather than a check that quietly skipped it.

A compose line the reader cannot classify stops the step at exit 3 with the line printed
verbatim. A YAML merge key is why: `<<: *common` can supply a `container_name` a line
scanner cannot see, so skipping it would assert a shape that was never read.

## Verify

Every service key in every compose file in the repo carries its file's compose project name
— equal to it, or opened by it and a hyphen — sits outside the generic set, and equals its
own `container_name`, which must be set. Every `*.caddy` basename sits outside the generic
set too, because a vhost copied into the proxy's shared `conf.d` is separated from its
neighbours by nothing else, and a matching basename overwrites theirs at the next reload
with a config that validates perfectly.

The `Caddyfile` itself is not asserted. It is the base config of a proxy the repo owns, it
is never copied into somebody else's directory, and its name is fixed by Caddy.

The vhost half asserts a non-generic basename rather than a project-prefixed one, which is
what the fleet measures: the host repo keeps a draft of a tenant's vhost to be diffed
against theirs, so that file carries the tenant's name and not the host's own. A
repo-local check cannot see that two repos picked the same basename in any case — refusing
the generic ones is the whole of the cross-repo protection a single-repo check can offer.

The scan is not narrowed to services that join an `external:` network, which is how the
commit-time lint scopes the same rule. One tenant here is the reason: two of its services
declare no `networks:` key at all, and the host's compose file joins that tenant's default
network to reach them, so the proxy straddles the bridge those two sit on. The original incident had
its two claimants of `app` on different bridges with the proxy across both, which is
exactly what a per-network reading reports clean.

It cannot pass vacuously. A repo with no compose file is exit 2 — the shape is unobservable
rather than satisfied — which sends `/adopt` on to probe, where the absence of a vhost and
a publish config as well is what makes it a decided `n/a`. A compose file whose services
cannot be read is exit 3 with the line named, never a pass.

## By hand, after the script

- Assert identity rather than liveness, which no script here can do: the publish has to check
  this app's own marker is present *and* every other tenant's marker is absent. A status
  code, a `Server` header and the certificate all stay correct while the proxy routes to the
  wrong app, which is why every conventional check stayed green for 41 hours. The
  `IDENTITY_CHECK` key in `config/publish.env` is where that assertion is wired, and the
  recorded note for this step never claims it was checked.
- Read the references the step could not see. It searches this repo's compose files, its
  `*.caddy` vhosts and `config/publish.env`, and nothing else — a deploy script, a
  Dockerfile, a runbook or a systemd unit on the box can name a service too. In a
  transcrypt-locked checkout `config/publish.env` reads as ciphertext, so unlock it before
  trusting that list.
- Recreate the one service rather than the stack. After the edit, on the box:
  `docker rm -f <old-container>` then `docker compose up -d --no-deps <new-service-name>`,
  so one-shot siblings like a migration step do not re-run. Volumes are named after the
  compose *project*, so renaming a service keeps the data — renaming the project does not,
  and that is a different and unsafe edit.
- Check any service that genuinely scales. A service running more than one replica cannot
  carry a `container_name` at all, so for that one the finding is the wrong instruction.
  Record it as `declined` with that reason rather than working around the check.
