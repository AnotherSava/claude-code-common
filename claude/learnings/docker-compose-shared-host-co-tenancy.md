# Several compose projects on one host behind a shared reverse proxy

Running two or more independent compose stacks on one box, fronted by a single Caddy that each project drops a
vhost into. The pattern works, but the failure modes are all *silent* — nothing errors, the wrong thing just
starts serving. Learned the hard way when a commercial storefront spent 41 hours serving a completely
different application.

Companion notes: `tailscale-docker-caddy-gating.md` (the `remote_ip` gate and split-DNS),
`nextjs16-prisma7-docker-deploy.md` (compose project naming, per-repo deploy keys), and
`caddy-reverse-proxy-restart-window.md` — a tenant's own upstream restart, which is one tenant's
outage where recreating the proxy is everyone's, so the two stay apart.

## The shape

- **One network per tenant**, each created outside every project so no stack's `down` can delete it:
  `docker network create <tenant>-edge`. Each compose file declares its own, `external: true`.
- The proxy joins every tenant's network **plus** its own project network. A tenant's app joins its own network
  and its own project's internal one, so the proxy is the only container outside that project that reaches it.
- Each project ships its own vhost file, copied into a directory the proxy imports
  (`import /etc/caddy/conf.d/*.caddy`), and reaches its app **by container name**.

Put every tenant on one shared `edge` instead and each of them reaches all the others' apps directly, past
every rule in any vhost — the authentication-bypass landmine below. Splitting a shared network costs one
container recreation per tenant and no vhost change, since the proxy resolves the same container name on the
new network, and tenants can move one at a time.

## Landmine 1: the compose *service* name becomes a DNS alias on every network it joins

This is the one that caused the outage. Compose registers **both** the container name and the **service** name
as network aliases, on *every* network the service is attached to. `container_name:` adds an alias; it does not
suppress the service-name one, and there is no way to turn it off (`networks.<net>.aliases` only ever adds).

So two projects that both call their service `app` publish an `app` alias each, and the proxy resolves `app` to
whichever Docker's embedded DNS hands back — walked in sandbox endpoint order, and not something you control.
Separate networks do not separate the two claims: a resolver searches every network its own container is
attached to, so the proxy straddling both is all it takes. A third claimant arrives if the proxy's *own* vhost
uses a bare `app:3000` for its own service on its private network.

Measured 2026-10-08 on Docker 29.5.2, with two throwaway containers aliased `app` on their own networks and a
third joined to both: the straddling container answered with one tenant's address on every query, and with the
same one from a second container attached in the reverse order — so attachment order is not the lever. It
switched to the other tenant only once that network was disconnected from it, so the resolver namespace is
exactly the union of the networks the asking container holds. Which rule picks the winner was not established.

```bash
docker network create t1
docker network create t2
docker run -d --name t1-app --network t1 --network-alias app alpine:3.20 sleep 900
docker run -d --name t2-app --network t2 --network-alias app alpine:3.20 sleep 900
docker run -d --name probe --network t1 alpine:3.20 sleep 900
docker network connect t2 probe
docker exec probe getent hosts app      # one address, and nothing says which of the two it is
```

What it looks like: the storefront returns HTTP 200 with a perfectly healthy page — belonging to the neighbour.
No error anywhere. The proxy re-resolves a static upstream on every dial, so it needs no restart to flip, and
nothing in any log says the name was ambiguous.

**Diagnose:**

```bash
# What names does this container actually answer to on that network?
docker inspect <container> --format '{{json .NetworkSettings.Networks.<net>.Aliases}}'
# → ["tracker-app","app"]        ← the second one is the trap

# What does the proxy actually get when it resolves the name in its vhost?
docker exec <proxy-container> getent hosts app
# compare against each candidate's IP:
docker inspect <container> --format '{{.NetworkSettings.Networks.<net>.IPAddress}}'
```

**Fix — name the service the same as its container, and never generically:**

```yaml
services:
  calendar-app:                   # NOT `app`
    container_name: calendar-app  # both aliases collapse to one unambiguous name
    networks: [default, calendar-edge]   # this tenant's own, not a bridge shared with neighbours
```

And in the proxy's own vhosts, reverse-proxy to **container names**, never to bare service names — a bare name
is only unambiguous until the next co-tenant arrives.

**Detect it — liveness checks structurally cannot.** Uptime monitoring, container healthchecks and
`caddy validate` were all green for the entire outage, because the app being served *is* healthy; it is simply
the wrong one. Only an identity assertion sees it, and it needs two halves — the second is the load-bearing one:

- **From outside, per hostname:** the host's own marker is PRESENT *and* every other tenant's marker is ABSENT.
  Derive the reject set from the tenant list rather than writing it out, so adding a co-tenant is one entry and
  every existing target learns to reject it in the same edit. The marker must be something the **origin app**
  emits — a `<title>` is ideal. Anything the proxy adds (status code, `Server` header, the TLS certificate)
  stays correct while the proxy routes to the wrong app, which is the whole failure. Run this **off the box**:
  an on-box checker shares fate with the thing it is checking.
- **On the box, structurally:** require every `reverse_proxy` upstream to resolve to a container *of exactly
  that name*. That single equality IS the rule "address co-tenants by container name", enforced rather than
  remembered, and it needs no list of expected values to keep in sync. Pair it with a check that no alias in the
  proxy's resolver namespace has more than one claimant — scoped to the **union** of the proxy's networks, not
  per-network: in the real incident the two claimants of `app` sat on *different* bridges with the proxy
  straddling both, so a per-network duplicate check reports CLEAN on the very bug it is meant to catch.

Read the live adapted config (`caddy adapt`), not the source file, so imported co-tenant vhosts are included.
Note that `docker inspect -f '{{...Networks.<name>...}}'` cannot express a hyphenated network name — a Go
template field selector rejects the hyphen — so index the inspect JSON instead of templating it.

**Working implementations exist — reuse them rather than rebuilding.** All stdlib-only Python 3, no deps:

| What | Where | Layer | Wired in |
|---|---|---|---|
| `ingress-lint.py` | the dotfiles `scripts/` dir (global) | prevent, per repo | **nothing yet — run it by hand or from a repo's `commit-checks.sh`** |
| `ingress-lint.py` (hook adapter) | the dotfiles `hooks/` dir (global) | the same check, on `PostToolUse` | **written and tested, not registered** — see below before writing another |
| `verify-tenancy.py` | the proxy-owning project's `bin/` dir, reaching the box as `/opt/landlord/bin/verify-tenancy.py` — no tenant keeps a copy | on-box structural check | run by hand |
| `identity-check.py` | the dotfiles `scripts/` dir (global) | external identity assertion | every publish, via `IDENTITY_CHECK` |
| the per-host identity manifest | emitted on the box by `/opt/landlord/bin/host-manifest`, which publish finds with `test -x` over the ssh connection it already holds and then runs there | the per-host data the checker reads | the same `IDENTITY_CHECK` string |

**The lint is repo-local and cannot see a collision between two repos** — it catches "this repo claims a generic
name", never "these two repos claim the same one". That gap is covered downstream: `verify-tenancy.py` sees the
whole box, and `identity-check.py` sees what the internet sees. Which is why the denylist half is the part that
must hard-fail: refusing generic names is the only cross-repo protection a single-repo static check can offer.

`ingress-lint.py` is stdlib-only because hooks run `python -S`, which drops site-packages and would make PyYAML
unimportable — so it carries a small hand-rolled reader for the compose subset it needs.

**The hook adapter already exists**, at `hooks/ingress-lint.py`. Read it before writing one: it loads the rules
from the `scripts/` copy by path rather than duplicating them, and it is tested against every payload shape
(violating file, clean file, unwatched path, missing file, malformed stdin, empty payload) plus a second
tenant's real compose. What it is **not** is registered — `settings.json` names it nowhere, and that is a
pending decision rather than an oversight, because registering changes every tool call in every session. The
exact entries to add are in the adapter's own docstring. Its shape, and why:

- **`PostToolUse`, matcher `^(Write|Edit)$`**, not `PreToolUse`. The lint has to read the file's *new* content,
  which only exists on disk after the write; a pre-write hook would have to parse tool input instead. It also
  has nothing to block — it needs to tell you what you just broke, which is what a post hook does. (Contrast a
  secret-guard, which genuinely must be `PreToolUse` because a leak cannot be un-written.)
- **Gate with the `if` field, not with a check inside the script.** `"if": "Write(//**/docker-compose*.yml)"`
  costs zero process startup when it does not match, where an in-script early return has already paid for the
  interpreter. The `//` root anchor is mandatory — without it the rule matches nothing and the hook silently
  never runs, so verify it fires rather than assuming. Keep a basename check in the script anyway, so it stays
  correct if the matcher is ever widened. One `if` names one tool and one pattern, so this needs an entry per
  pattern.
- **Report through `additionalContext`, not an exit code.** Exit 0 with `hookSpecificOutput.additionalContext`
  on stdout is how a `PostToolUse` hook reaches the model; exit 2 also works but blocks, and a hook marked
  `async` cannot deliver context at all. Exit 0 on every path, including failure — a hook that throws breaks
  every tool call in the session.
- **A hook only sees edits made through the tool.** Hand edits in an editor, and anything changed directly on
  the box, bypass it entirely — so a repo's `commit-checks.sh` calling the same global script is a complement,
  not a duplicate. Call the global path from there; never fork a per-repo copy, which is exactly how two copies
  start drifting.

Run all three against the *known-bad* state before trusting them: pointing `identity-check.py` at a manifest
whose entry names the wrong URL replays the misroute exactly, standing two throwaway containers on two throwaway
networks with a shared alias reproduces the collision, and linting a lone `.caddy` file checks that the
cross-file rule still fires. All three caught real defects in the checkers themselves the first time they ran —
the last one most recently: given a single file the lint could not see the repo's compose services, so the
"upstream is a service name" rule silently could not fire and it printed "clean". It now resolves the repo root
from whatever path it is handed and judges with the full service map, reporting only on the files named.

**Wire the identity assertion into the publish rather than leaving it a thing to remember.** The shared
`publish-ssh-compose.sh` takes an `IDENTITY_CHECK=<command>` key in `config/publish.env`: it runs locally after
the URL checks, and a non-zero exit fails the publish. Without it a publish verifies liveness only — a real page
returning 200 — which is precisely the check that stayed green for the whole outage. Every project on a
shared-proxy box should set it. In the same file, leave `VHOST_DIR` **unset** when the repo owns the proxy
instead of renting a vhost inside someone else's; otherwise the publish copies the proxy's own config onto
itself. `VHOST_SRC` alone still answers "did it change", which is what decides the force-recreate.

Renaming a *service* is safe: volumes are named after the compose **project**, not the service, so data
survives. Recreate just that one service with `--no-deps` so one-shot siblings (`migrate`, a seed step) do not
re-run:

```bash
docker rm -f <container>            # the old container belongs to the now-renamed service
docker compose up -d --no-deps <new-service-name>
```

**The `rm` has to come first whenever the renamed service's container name differs from the old container's.**
A rename that gives a service the name its container already carried makes the next `up` abort on `Conflict. The
container name … is already in use`, which is safe. Any other name does not conflict, whether the old container
ran under a derived `<project>-<service>-1` or an explicit `container_name` the rename also changed: a plain
`docker compose up -d` — which is what the shared publish script runs — starts the renamed service beside the old
container and only warns about orphans. The old one keeps running, still answering to its old aliases. For a
database service that means two servers opening the same named volume, since the volume is keyed by the project
and not the service. It also keeps every host port it published, and a `restart: unless-stopped` policy brings it
back with the Docker daemon after a reboot. Measured 2026-10-06 on a dev database renamed with both names
explicit: the orphan returned at the next Docker start still publishing `0.0.0.0:5432`, so the renamed service's
`127.0.0.1:5432` could not bind. Remove every old container before the first `up` after the rename, or make that
one `up -d --remove-orphans`.

**Do that recreate immediately, because until it happens the OLD name still resolves.** A running container
keeps the aliases it was created with; editing the compose file changes what the *next* container answers to
and nothing about the one already up. So every consumer still dialing the old name keeps working, the rename
looks complete, and the breakage is deferred to whatever recreates the container next — a deploy, a host
reboot, an unrelated `up -d` weeks later.

Measured 2026-09-20: a service renamed `mongo` → `<tenant>-db` on 2026-09-03 went on answering to `mongo` for
**17 days**. The container was recreated at 04:36; the nightly backup, whose credential file still said
`mongo`, had succeeded at 04:10 that morning and failed from the next run on, with
`lookup mongo on 127.0.0.11:53: server misbehaving`.

Two things follow:

- **The grace period is the danger.** A rename that broke instantly would be caught by whoever did it. One
  that breaks at an arbitrary later moment arrives detached from its cause, in whatever component nobody
  thought to re-render.
- **The copy that breaks is the one nothing regenerates.** That app's URI came from a secret manager and
  changed with the rename; the backup's came from a one-off render command in a runbook, so it aged in place.
  After renaming a service, grep the box for the old name rather than trusting the file you edited:
  `grep -rl <old-name> /etc/<tenant> /opt/<tenant>`.

## Landmine 2: `environment:` beats `env_file:` even when the value is empty

Compose interpolation (`${VAR}`) reads the shell and a file named exactly `.env` in the project directory —
**never** an `env_file:`. An unset variable interpolates to an empty string, and `environment:` outranks
`env_file:` *even when the resulting value is empty*. So this quietly blanks the real credentials:

```yaml
    env_file: app.env            # POSTGRES_PASSWORD=s3cret lives here
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}   # ← unset in the shell → "" → wins
```

Postgres then refuses to initialize an empty volume ("superuser password is not specified"), never goes
healthy, and every `depends_on: condition: service_healthy` hangs behind it.

Verified directly rather than from docs:

```bash
printf 'FOO=from_env_file\n' > test.env
# compose file with env_file: test.env AND environment: FOO: ${FOO}
docker compose config | grep -A2 environment     # → FOO: ""
docker compose run --rm t                        # → FOO=[]
```

The trap hides in plain sight because the *dev* compose file usually gets away with the identical shape — it is
launched through something like `doppler run -- docker compose up`, which really does put the values in the
shell. Production has no such wrapper.

**Fix:** delete the `environment:` block and let `env_file:` be the only source. Don't "fix" it by adding
`--env-file` to the up command — that has to be remembered on every subsequent invocation, and forgetting it
silently reintroduces the blank override. Note that a healthcheck referencing the same vars needs `$$` so
expansion is deferred to the container's shell: `pg_isready -U $${POSTGRES_USER}`.

## Landmine 3: two projects, one filename in the shared conf.d

Repos tend to call their vhost something generic like `deploy/site.caddy`. Copying that into the shared
directory without renaming **overwrites the neighbour's vhost** and takes their site off the internet at the
next reload — with a config that validates perfectly. Always rename on the way in
(`cp deploy/site.caddy /opt/caddy-conf.d/<project>.caddy`); the import glob doesn't care what the file is
called, only that two projects don't pick the same name.

## Landmine 4: an unvalidated file in conf.d is live from the next *start*, not the next reload

The vhost has to be in the imported directory before it can be validated, because the import is what puts it in
context. If validation fails and you merely skip the reload, everything looks fine — until the box reboots or
the proxy's own stack is brought up, at which point the proxy cannot parse its config and restart-loops, taking
**every** co-tenant down with nothing pointing back at the deploy that did it. Make the removal atomic:

```bash
cp deploy/site.caddy /opt/caddy-conf.d/myapp.caddy
docker exec <proxy> caddy validate --config /etc/caddy/Caddyfile \
  || { rm -f /opt/caddy-conf.d/myapp.caddy; echo REVERTED; }
docker exec <proxy> caddy reload --config /etc/caddy/Caddyfile
```

Also note `validate` parses the *whole* config, every co-tenant's file included — so a failure may be somebody
else's, and blindly removing your own file won't clear it. Re-validate after removing to confirm whose it was.

## Landmine 5: the shared network is an authentication bypass

Every access rule enforced at the proxy — basic auth, IP gates, path 404s — is bypassed entirely by anything
sharing a network with the app, which dials it by container name on its own port. `expose:` documents a port;
it restricts nothing. For an app whose only access control lives in its vhost, membership of that network *is*
full access.

**Give each tenant its own network rather than vetting who shares one.** Trust does not hold the line: a
co-tenant you trust is also whatever its next dependency pulls in, and nothing in your own repo can restrict
what a container on the same bridge does. With one network per tenant the only other member is the proxy, so
the bypass has nobody to serve.

That does not relax Landmine 1. The proxy joins every tenant's network, so its resolver namespace stays the
union of all of them, and a generic service name still collides across two bridges it straddles. A service name
has to be unique across the proxy's whole set, whichever single network the service itself sits on.

**Move the tenants one at a time and drop the shared bridge last.** Running `docker network connect <net>
<container>` attaches a live proxy to a new network with no restart, so it can sit on the shared bridge and
every per-tenant one at once while tenants migrate in any order. Each tenant's own half is one line in its
compose file, and it takes effect when that tenant's next deploy recreates the container — until then the old
reach is still open whatever the file says. The shared network comes off the proxy once the last tenant has
left, and only then can a check refusing any network carrying two tenants be switched on: added sooner it is a
true violation, and one red verdict refuses every tenant's publish rather than the offender's.

**A checker keyed on the shared network's literal name goes blind on the tenant that moves.** The rules that
matter most about a joined network — a `container_name` equal to the service name, no generic name — are gated
on membership of it, and a predicate matching the old name skips the moved service while still reporting that
names agree. Key it on `external: true` in the top-level `networks:` block instead, which is what says this
project joins a network rather than owning it, and is as true of a two-party bridge as of a host-wide one.

**Assert the route a neighbour has lost, with the positives in the same command.** Every other probe here runs
from the tenant's own side and asks whether the right thing answers; none of them can see the property the split
buys, which is that a neighbour no longer reaches the app at all. Docker's embedded DNS answers a name only for
a container sharing a network with the target, so one resolver asked for several names separates the two
states — provided the same invocation includes names it *does* share a network with. Those are the control: a
later run that loses them is reporting a broken instrument, and without them a uniformly negative answer and a
dead probe are the same output.

```bash
docker exec <a-tenant-container> node -e '
const d=require("dns");
for (const n of ["<a name it shares a network with>","<another>","<a moved tenant>","<another>"])
  d.lookup(n,(e,a)=>console.log((e?"NO-ANSWER "+e.code:"RESOLVED  "+a).padEnd(22), n));
setTimeout(()=>process.exit(0),6000);'
```

Node rather than `getent`, which these images do not carry; the proxy's image does, which is why an on-box
checker running there can use it and a tenant container cannot. Name the controls by that property rather than
by container, because membership moves as tenants migrate and a hard-coded pair rots into a false alarm. Read
answer against no-answer and not the error code: verified 2026-10-08 on two throwaway networks, the negatives
came back `ENOTFOUND` where a real split host reported `EAI_AGAIN` for the same situation.

**A reachability probe shaped `wget … && echo REACHABLE || echo UNREACHABLE` proves nothing.** With `-q` and
stderr discarded, every non-zero exit collapses into one word, so an absent route, a refused port, a 404 and a
redirect are indistinguishable — and so is a missing binary. Measured 2026-10-08 from a container that had
`wget`, on a network it shared with the target, resolving that target's name to an address: the probe still
printed `UNREACHABLE`, because nothing was listening on the port. A negative from this shape is not evidence
about the network.

## Caddy `basic_auth`, for gating an app that has no sign-in yet

```caddyfile
@gated {
	not path /feed/*                                    # carve-outs for machine clients
	not remote_ip 100.64.0.0/10 fd7a:115c:a1e0::/48     # and for the tailnet
}
basic_auth @gated {
	username $2a$12$...
}
```

- Conditions inside a named matcher are **AND**ed; `not` inverts. Path wildcards **do** cross `/`, so
  `/feed/*` matches `/feed/<token>/calendar.ics`.
- Renamed from `basicauth` in **v2.8.0**.
- **Directive order is fixed by Caddy, not by file order**: `basic_auth` runs *before* `respond` and
  `reverse_proxy`. So a `respond @x 404` rule meant to hide a path is answered by the auth challenge first —
  an unauthenticated probe gets 401, and only a request that already has the password reaches the 404. Both
  rules still earn their place; neither replaces the other.
- **Hash format:** `caddy hash-password` emits `$2a$`. `htpasswd -bnBC 12` emits `$2y$`, and sources disagree on
  whether Caddy accepts it. The two are byte-identical bcrypt, so normalize rather than gamble:
  `htpasswd -bnBC 12 user "$PW" | sed 's/\$2y\$/$2a$/'`.
- Cost 12 means the proxy burns ~250 ms of CPU per *wrong* password, on a box shared with other tenants — a
  cheap denial-of-service lever for anyone who knows the hostname. Worth weighing against a lower cost when the
  passphrase itself has high entropy.

**Test the vhost's logic before it goes near the shared proxy.** Adapt the real file — swap only the site
address and the upstream — and run it locally:

```bash
sed -e 's|^example\.com {|{\n\tauto_https off\n}\n:8899 {|' \
    -e 's|reverse_proxy myapp:3000|respond "APP OK" 200|' site.caddy > /tmp/t.caddy
caddy start --config /tmp/t.caddy --adapter caddyfile
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8899/feed/x/calendar.ics   # expect 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8899/                      # expect 401
caddy stop
```

This catches matcher and ordering mistakes in seconds, without a reload that could take down a neighbour.

## Landmine 6: `docker compose build` on the production box overwrites the production image tag

A service with a `build:` block and no `image:` key gets its tag *derived* from the project name — project
`storefront` plus service `app` becomes `storefront-app:latest`, the exact tag the running container was created
from. So any experimental build in that directory silently replaces the production image. Nothing warns, the
running container keeps serving the old one, and the swap is only realised at the next unrelated
`docker compose up -d`, which adopts the experimental image and deploys code that was never published.

Same shape as Landmine 3: a name derived from context rather than declared, colliding with something that
matters.

Build under an isolated project name instead. The `-p` flag beats the file's top-level `name:`, and a compose
file trimmed to just the services you need keeps missing `env_file`s and `${VAR}` interpolation out of the way:

```bash
docker compose -f docker-compose.probe.yml -p myprobe build   # tags myprobe-app, not storefront-app
```

Prove it rather than trusting it — record the tags before and after, and assert they are unchanged:

```bash
docker images --format '{{.Repository}}:{{.Tag}}  {{.ID}}' | grep -E '^(storefront|calendar)-'
docker inspect <container> --format 'image={{.Image}} restarts={{.RestartCount}}'
```

Two related traps while cleaning up after such a build:

- **`docker builder prune --filter until=1h` removes cache _older_ than 1h** — i.e. everyone else's, not the
  cache you just created. Reading it as "mine, from the last hour" deletes a co-tenant's build cache. Nothing
  breaks (cache is reconstructible) but their next build is slow and the surprise is yours to explain.
- **`docker build` pulls the base image if it is absent**, and on a shared box that base is likely a
  neighbour's production base too. Benign when the digest matches; a tag that has moved upstream silently
  re-points what the next publish builds on. Check `docker image inspect <base> --format '{{.Metadata.LastTagTime}}'`
  — and read it in the *box's* timezone, not yours, before concluding a pull did or didn't happen.

## Landmine 7: `down -v` deletes the certificate volume, and one flag is the whole distance

A shared proxy's data volume holds every provisioned certificate on the box — on a three-tenant host that is
eight names across two registrable domains. Let's Encrypt caps *duplicate* certificates at five per week, so
losing them is not a re-run; it is an outage with a waiting period, on the one machine every tenant watches.

`docker compose down -v` removes every volume declared in the top-level `volumes:` section. `down` is an
ordinary maintenance command and `-v` is one character.

Three routes, and only the last is bad luck:

- **`down -v`** — deletes named project volumes, by design and without a prompt.
- **`docker volume prune -a`**, or `docker system prune -a --volumes`. A *bare* `prune` spares named volumes
  (Docker 29 takes only anonymous ones without `-a`), but `-a` removes any volume with no container attached
  — which is precisely the state during a maintenance window.
- **Changing the project name.** Volumes are `<project>_<key>`, so editing `name:` at the top of the file
  points the stack at a fresh, empty volume and the proxy re-issues everything. Nothing is deleted and
  nothing warns. This qualifies the "renaming a service is safe" note above: renaming a *service* is,
  renaming the **project** is not.

The fix is the one already applied to the tenant networks — declare it external, create it out of band, so no
stack's `down` can reach it:

```yaml
volumes:
  caddy_data:
    external: true
    name: storefront_caddy_data     # WITHOUT this, compose looks for a volume literally called
  caddy_config:                     # `caddy_data`; the existing data is `<project>_caddy_data`
    external: true
    name: storefront_caddy_config
```

```bash
docker volume create storefront_caddy_data     # once per host, before the first `up`
```

Two things to do rather than assume:

- **Check it does not recreate.** `docker compose up -d --dry-run` should report the containers as merely
  `Running`. Converting an in-place volume to external under the same underlying name is inert for a running
  stack — but confirm it, because a recreate here interrupts every tenant at once.
- **Prove the protection in a scratch project**, never in production: declare one external and one managed
  volume, `up --no-start`, `down -v`, and see which survives. Ten seconds, and it turns "should" into "does".

Then **pin it with a test**, because the hardening is invisible: deleting `external: true` changes nothing
observable, `up` keeps working against the same data, and the loss only appears the day someone runs
`down -v`. An assertion that every declared volume is external is what stops it being tidied away.

## Landmine 8: the repo directory name is not the deploy path, and a systemd unit will not tell you

Every tenant on this shape deploys to `/opt/<tenant>`, while its git repo is a directory named whatever the
repo is called. Those differ more often than you would expect — a project renamed after its first commit, or
a repo named for the product and a tenant named for the hostname. Inside the repo the difference is invisible,
because everything there is relative. It becomes real the moment a file has to name an **absolute path on the
box**, and a systemd unit is the worst place for that to go wrong:

```ini
ExecStart=/opt/<repo-directory>/deploy/backup.sh     # WRONG, and silent
```

`systemctl enable --now` succeeds. `systemctl list-timers` shows the timer scheduled. `systemctl status`
reports it loaded and waiting. Nothing is wrong until it *fires*, and then it dies instantly as `203/EXEC`
at whatever hour you chose — which for a nightly backup means the failure is discovered by needing a restore.

A real instance shipped this way for two days and was caught only because the install was done by hand. Had
it been installed as written, the observable state would have been a healthy-looking timer and no backups.

Assert it in whatever gate the repo already has, in two halves — either alone leaves the hole open:

```python
# 1. no file may name /opt/<repo-directory> in a directive
#    (build the needle from os.path.basename(root) so the checker does not flag its own source)
# 2. a unit's ExecStart must live under /opt/<tenant> AND resolve to a file that exists in the repo,
#    so renaming the script fails the commit rather than the timer
```

The second half is the one that keeps paying: it catches a *correct* prefix pointing at a script that has
since been renamed or moved, which no amount of string-matching on the wrong name would find.

Two notes from implementing it. Exempt `#`-comment lines in non-markdown files, or a unit's own "NOT
/opt/<repo>" warning comment fails the check it documents — but do **not** exempt markdown, or prose quietly
reintroduces the wrong path into the runbook someone will copy from. And verify the rule can *fail*: break
the path deliberately, break the filename deliberately, and confirm each shape is reported. A path check that
silently matches nothing passes forever.
