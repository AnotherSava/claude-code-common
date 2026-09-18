---
title: Compose services carry the project's name
rules: cotenant-service-names
---

## What changed

Docker compose publishes a *service's* key as a DNS alias on every network that service joins,
shared ones included, and `container_name:` adds an alias rather than replacing it. So two projects
that each call a service `app` both answer to `app` on the bridge they share, and the proxy dials
whichever the daemon hands back — walked in sandbox endpoint order, which nobody controls. In August
2026 that put a commercial storefront on a neighbour's application for 41 hours, at HTTP 200, with
healthy containers, a valid config and every uptime check green throughout. The mechanics, and the
checkers already written against them, are in
`learnings/docker-compose-shared-host-co-tenancy.md`.

The shape this asks for is one name per thing: a service key that carries its project's name, a
`container_name` equal to it, and a vhost basename no neighbour would also pick.

**This one detects and never edits.** A compose service name is dialled from `depends_on`, from
another service's environment, from the vhost's `reverse_proxy` upstream, from `BUILD_SERVICES` and
`APP_CONTAINER` in an encrypted `config/publish.env`, and from the derived container name a proxy
holds when no `container_name` is set. A rename that misses one of those does not error: it serves
the wrong thing behind an HTTP 200, which is the failure this convention exists to prevent. So find
the deviation, name it, and print the references you can see; the edit is a human's.

## Migrating an existing repo

There is a finding here when a compose file holds a service key inside the generic set, a key that
does not carry its compose project's name, a key with no `container_name` or one that differs from
it, or when a `*.caddy` basename sits inside the generic set. Name the file, the line, the name it
should carry, and the rule it breaks, together with every reference in this repo the rename has to
reach — the compose files, the `*.caddy` vhosts and `config/publish.env` — then put it to the user.
Change no compose file on their behalf.

Read the generic set from `claude/scripts/ingress-lint.py`, which already refuses those names at
commit time, imported rather than copied so the two cannot disagree about what generic means, plus
`mongo` and `migrate` — two names the fleet's own compose files use and that list does not carry.
When the import fails, say so and refuse to judge, rather than falling back to a second copy of the
list.

Three more states are a question rather than a finding:

- **A compose file with no top-level `name:`** — the compose project name is then derived from
  whatever directory the stack is brought up in, so the prefix every service should carry has no
  stable value to check against. Ask for a `name:` naming the project, or for confirmation that the
  stack is deliberately brought up under varying names.
- **Compose files with no service key in any of them**, which leaves nothing for the convention to
  be true or false about. A fragment or an override that only ever extends another stack is the
  usual reason.
- **A compose file that cannot be opened at all.** Report it as the question, never folded into "no
  compose file here", which would turn an unreadable tenant into a repo that deploys nothing. Unlock
  or repair the file and start again.

Read a dev-only compose file like any other, and name a generic key in one. That is deliberate: one
tenant here is the measured case where "it is not on the shared bridge today" was the defence, while
the host's own compose file joins that tenant's default network to reach exactly those services.

A compose line that will not classify stops the work, with the line printed verbatim. A YAML merge
key is why: `<<: *common` can supply a `container_name` a line scanner cannot see, so skipping it
would assert a shape that was never read.

Afterwards:

- Assert identity rather than liveness, which no check here can do: the publish has to confirm this
  app's own marker is present *and* every other tenant's marker is absent. A status code, a `Server`
  header and the certificate all stay correct while the proxy routes to the wrong app, which is why
  every conventional check stayed green for 41 hours. The `IDENTITY_CHECK` key in
  `config/publish.env` is where that assertion is wired, and nothing here claims it was checked.
- Read the references no scan can see. This searches the repo's compose files, its `*.caddy` vhosts
  and `config/publish.env`, and nothing else — a deploy script, a Dockerfile, a runbook or a systemd
  unit on the box can name a service too. In a transcrypt-locked checkout `config/publish.env` reads
  as ciphertext, so unlock it before trusting that list.
- Recreate the one service rather than the stack. After the edit, on the box:
  `docker rm -f <old-container>` then `docker compose up -d --no-deps <new-service-name>`, so
  one-shot siblings like a migration step do not re-run. Volumes are named after the compose
  *project*, so renaming a service keeps the data — renaming the project does not, and that is a
  different and unsafe edit.
- Check any service that genuinely scales. A service running more than one replica cannot carry a
  `container_name` at all, so for that one the finding is the wrong instruction, and the convention
  needs the exception written into it rather than worked around in the repo.

## When it does not apply

The repo holds no compose file, no `*.caddy` vhost and no `config/publish.env`. Those three absences
together are positive evidence that this repo deploys nothing to the shared box today, so it claims
no name in a namespace another project writes to. Ten of the fleet's repos answered this way when
this version was written.

It is a fact that expires, which is why the rule below runs on every commit rather than the reading
standing on its own: the first of those repos to become a tenant surfaces as a finding rather than a
silence.

## Continuing rule

`cotenant-service-names` — every service key in every compose file in the repo carries its file's
compose project name (equal to it, or opened by it and a hyphen), sits outside the generic set, and
equals its own `container_name`, which must be set; and every `*.caddy` basename sits outside the
generic set too, because a vhost copied into the proxy's shared `conf.d` is separated from its
neighbours by nothing else, and a matching basename overwrites theirs at the next reload with a
config that validates perfectly. The `Caddyfile` itself is not asserted — it is the base config of a
proxy the repo owns, it is never copied into somebody else's directory, and its name is fixed by
Caddy. The scan is not narrowed to services that join an `external:` network, which is how the
commit-time lint scopes the same rule: one tenant's services declare no `networks:` key at all while
the host's compose file joins their default network, and the original incident had its two claimants
of `app` on different bridges with the proxy across both — exactly what a per-network reading
reports clean.
