# A `tailscale serve` port is a claim on the whole machine

A dev server that refuses to start with `EADDRINUSE` while `lsof` and `netstat` both show the port free has a
holder outside the view a normal process listing gives. On macOS the usual one is Tailscale: `tailscale serve
--https=N` puts its listener in a root-owned system extension, so an unprivileged listing prints nothing about
a port nothing can bind. Five restart attempts and a log read went into one of these before anyone tried a
bind directly.

Everything below was measured on macOS, tailscale 1.102.1, 2026-10-05, on scratch ports in the 41xxx range.

## What the mapping takes

`tailscale serve --yes --bg --https=N http://127.0.0.1:N` returns 0 and prints its URL. While it stands:

| Bind | Result |
|---|---|
| `0.0.0.0:N` | fails, errno 48 |
| the node's tailnet address, v4 and v6 | fails, errno 48 |
| `[::]:N` | fails, errno 48 |
| `127.0.0.1:N` | succeeds |
| `[::1]:N` | succeeds |

So the mapping is a claim on this machine's port space, not only on the tailnet's. Loopback is the one address
it leaves free, which is why a loopback-only origin can share its number and nothing else can.

`lsof -nP -iTCP:N -sTCP:LISTEN` returns empty for the whole of that window. The holder is
`/Library/SystemExtensions/.../io.tailscale.ipn.macsys.network-extension`, running as root. `netstat -an -p tcp`
is no help either — in Git Bash on this machine it emits zero lines for every port, so it proves nothing about
any of them.

`tailscale serve --https=N off` frees the port on the first poll, every time, across four measurements — two of
them after a proxied request had gone through the mapping. There is no hold-down period to design around.

## Why the same number on both sides fails on the second run

Creating a mapping over a server that is already listening works, and that is what makes the trap quiet.
Measured: with `python3 -m http.server N --bind 0.0.0.0` up, the serve command returned 0 with empty stderr,
the proxied `GET` returned 200 with the right body, and the origin's own access log recorded the request
arriving from `127.0.0.1` — so it really did traverse tailscaled rather than hit the origin's wildcard socket.

The failure arrives one restart later. Kill the origin, leave the mapping, and a wildcard rebind of that port
fails with errno 48. For `next dev` that is terminal: retry is gated on `portSource === 'default'`, so a command
with an explicit `-p` prints `Failed to start server` and exits 1 rather than moving to the next port.

The asymmetry is the whole mechanism — a wildcard origin and a loopback origin behave differently on a shared
number, and a publish that succeeded is no evidence either way.

## Diagnosing it

```bash
python3 ~/.claude/skills/shared/port_probe.py verdict <port>
```

It pairs the process listing with a real `bind()` on `0.0.0.0`, and names a serve mapping when that is what
holds the port. The bind is the authoritative half: `SO_REUSEADDR` on both sockets does not let two wildcard
binds share a port — measured, errno 48 — while a wildcard listener and a loopback listener on one port do
coexist, so bind style changes the answer and a bare "is it free" question has two.

To clear a stale mapping: `python3 ~/.claude/skills/shared/tailnet_publish.py unpublish-port <port>`. It matches
on the target being a loopback proxy, so it will not touch a mapping something else created.

## Allocating the two numbers

A server reached over the tailnet needs the port it binds and the port the mapping fronts it on, and they have
to be different numbers unless the origin is loopback-only. Both come from the ports registry — `ports.py
allocate` — which records who owns each and refuses to hand either to something else. `publish-port <front>
--target <origin>` is the two-number form; `publish-port <port>` alone is refused over a wildcard-bound origin,
with the message naming the flag.

A mapping is write-once unless something removes it: it lives in tailscaled and survives reboots. The deploy
skill's `deploy-dev-server.sh` clears any mapping on `DEV_PORT` before it starts a server, which is what repairs
a project left in the wedged state by an earlier same-number publish.
