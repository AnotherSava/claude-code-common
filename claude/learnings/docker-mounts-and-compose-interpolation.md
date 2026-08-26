# Nested bind mounts, and how compose interpolation fails

Two Docker/Compose behaviours that are invisible until they aren't, both found by building a stack on a
real host rather than by reading the file. Companion: `docker-compose-shared-host-co-tenancy.md`.

## A nested read-only mount cannot create its own mountpoint

Mounting a directory read-only and then mounting something *inside* it is a normal shape — a config
directory owned by one party, with a sub-directory other parties write into:

```yaml
volumes:
  - ../../config:/etc/app:ro          # the base config
  - /opt/shared-conf.d:/etc/app/conf.d:ro   # a directory others drop files into
```

If `conf.d/` does **not already exist inside the source of the outer mount**, the container does not start
at all:

```
error mounting "/opt/shared-conf.d" to rootfs at "/etc/app/conf.d":
  create mountpoint for /etc/app/conf.d mount:
  mkdirat /var/lib/docker/rootfs/overlayfs/…/etc/app/conf.d: read-only file system
```

Because the parent is `:ro`, Docker cannot `mkdir` the mountpoint inside it. Pre-create an **empty**
`conf.d/` in the outer mount's source directory and the same two mounts work perfectly, with both layers
genuinely read-only (a `touch` in either is refused).

Two consequences worth planning for:

- **Git cannot commit an empty directory**, so whatever assembles that tree at deploy time has to create
  the mountpoint. A `.gitkeep` works for a checked-out tree; an assembled one needs the assembling script
  to do it.
- **The failure is at container *start*, not at config-change time.** A proxy that is already running keeps
  serving from memory, so the mistake is invisible until the next restart — which may be a reboot weeks
  later, with nothing pointing back at the change that caused it.

## Interpolation: literal fails closed, `${VAR}` fails **open**, `${VAR:?}` fails loud

Compose interpolates `${VAR}` from the shell and from a file named exactly `.env` — never from an
`env_file:`. An unset variable becomes an **empty string**, and compose only *warns*:

```
level=warning msg="The \"API_KEY\" variable is not set. Defaulting to a blank string."
```

`docker compose config` then exits **0**. Two ways that bites, both observed:

- **A credential renders as `""`** and the app starts with a blank one. If that credential is only used
  periodically — a certificate renewal, a nightly job — the failure surfaces weeks later, far from the cause.
- **A port binding loses its host IP entirely.** `"${TAILNET_IP}:53:53/udp"` with the variable unset does not
  become an invalid address; the `host_ip` key simply **vanishes** from the rendered config and the service
  binds `0.0.0.0`. A binding whose whole purpose was to keep a service off the public internet silently
  stops doing that. Verified both ways: with the variable set, `docker compose config` shows
  `host_ip: 100.x.x.x`; without it, no `host_ip` at all.

That gives a clear ranking, which is the useful part:

| Form | Behaviour when the value is missing |
|---|---|
| A literal (`"10.0.0.1:53:53/udp"`) | **fails closed** — a wrong or moved address simply refuses to bind |
| `${VAR}` | **fails open** — renders empty, warns, exits 0, and the protection disappears |
| `${VAR:?message}` | **fails loud** — exit 1, `required variable VAR is missing a value: message` |

So a bare `${VAR}` is the only unsafe form. Use it for nothing that is load-bearing.

`${VAR:?}` treats empty as missing, which is right for a credential. `${VAR?}` only requires the key to be
*present*, which is right for something a host may legitimately leave blank (an optional build-arg list) —
collapsing the two either forbids a real configuration or waves through a file that was never rendered.

A literal cannot be used by anything that has to run on more than one machine, which is the one real cost
of making a config multi-host: having given up the fail-closed form, it owes the fail-loud one.

## Building on a host you share with production

If you must build an image on a box that runs something else — to prove a Dockerfile works before a
cutover, say:

- Use a plain `docker build -t throwaway:tag`, not `docker compose build`. A compose service with a
  `build:` block and no `image:` key derives its tag from the **project name**, so building in a project
  directory silently replaces the production tag.
- `docker compose config` validates and renders **without creating anything**, so interpolation can be
  checked with no containers at all.
- Record the tag list *and* the dangling-image list before starting: a tag diff does not cover untagged
  layers, and other people's dangling images may be deliberate.
- A multi-stage build leaves its builder stage as a dangling image. Remove yours by ID; never by a filter
  like `--filter until=1h`, which selects everyone else's cache rather than your own.
- `docker build` pulls a base image only when it is absent, but the pull is worth reporting: check
  `docker image inspect <base> --format '{{.Metadata.LastTagTime}}'` and the daemon journal to see whether
  the tag moved to new content or merely re-stamped the same digest.
