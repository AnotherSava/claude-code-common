# Scoping a host-to-host service to the tailnet

Scoping a peer-sync HTTP listener that previously bound `0.0.0.0`, verified on macOS with Tailscale up,
2026-08-30. For the CIDR ranges themselves and the Caddy `remote_ip` form of the gate, see
`tailscale-docker-caddy-gating.md` — this covers the different problem of a service binding its *own*
sockets and checking its *own* peers.

## Bind narrowly and check the source — they are not alternatives

A narrow bind means the kernel never accepts the connection: the port is not even scannable from a hotel
LAN, and the HTTP parser is never reached. A source check means an off-scope caller is refused before any
credential is compared. Each covers what the other cannot:

- The bind cannot cover the **degraded** case (see below), a **stale** socket, or a route added later.
- The source check cannot stop the port being probed, and it runs only after a connection is accepted.

Run the source check *before* comparing the token, so an out-of-scope caller cannot even probe the secret.

## Detecting whether Tailscale is actually up

A CGNAT-range address does **not** prove Tailscale is running. `100.64.0.0/10` is the real carrier CGNAT
block and several ISPs assign it directly — Starlink, T-Mobile Home Internet, most mobile hotspots, some
hotel networks. On such a network with Tailscale **down**, a naive "is my local address in 100.64/10?"
check returns true for the *LAN* address, and a service that trusts it will bind that LAN address while
believing it scoped itself, then accept every host behind the same carrier NAT.

Cross-check against the route to the public internet. With a real tailnet the two differ; on carrier CGNAT
they are the same address, meaning there is no tailnet here:

```rust
let tailnet = route_source("0.0.0.0:0", "100.100.100.100:53");  // Tailscale's DNS
let public  = route_source("0.0.0.0:0", "1.1.1.1:53");
let real_tailnet = tailnet.is_some() && tailnet != public;
```

Measured with Tailscale up: `100.67.137.90` vs `192.168.1.97` — they differ, so the check is inert when
things are normal. An exit node makes them match, which degrades to a wide bind: the safe direction.

## Finding your own address without a crate or a shell-out

`connect()` on an **unconnected UDP socket** sends no packet; it just asks the kernel to resolve the route
and pins the local source address, which you then read back:

```rust
fn route_source(bind: &str, probe: &str) -> Option<IpAddr> {
    let sock = std::net::UdpSocket::bind(bind).ok()?;
    sock.connect(probe).ok()?;          // no traffic leaves the machine
    Some(sock.local_addr().ok()?.ip())
}
```

Beats `getifaddrs`/`GetAdaptersAddresses` (platform-specific, needs a crate) and beats shelling out to the
`tailscale` binary (may not be on PATH; parsing its output is a compatibility promise you did not want).

## The two failure modes a narrow bind introduces

**1. The startup race.** If the service autostarts at login it will usually beat the VPN. Binding
narrowly then fails outright and the listener never starts — the service is silently down until the next
restart, which is worse than a wide socket. Poll for a few seconds, then fall back to the wildcard bind
*and log loudly that you did*, keeping the source check as the remaining guard. Make the degraded state a
field on the plan, not an inference, so the warning cannot be forgotten.

**2. The socket outlives its address.** A socket bound to a specific address survives that address
disappearing (Tailscale logout, node-key reset, tailnet switch). The listener stays "bound", any
`is_listening` flag stays true, and every peer gets connection-refused until restart — with nothing
logged, because nothing failed. A wildcard bind cannot do this. Re-check the live addresses against the
bound set on an existing heartbeat and warn on divergence; latch it so a persistent divergence logs once.
Rebinding live is a much bigger change (graceful shutdown, plus a re-bind that can fail on a port still
held by lingering connections) and trades a rare miss for a rarer total outage.

## Widening to IPv6 makes latent v6 bugs reachable

`0.0.0.0` is **v4-only**, so any code path handling a peer address was implicitly v4-only too. The moment
you also bind the tailnet's `fd7a:115c:a1e0::/48` address, every such path runs with v6 for the first time.

The one that bit: an IPv6 literal must be **bracketed** in a URL, or the trailing `:<port>` parses as
another hextet.

```
http://fd7a:115c:a1e0::8735:895b:9078/...    -> InvalidPort
http://[fd7a:115c:a1e0::8735:895b]:9078/...  -> ok
http://::1:9078/...                          -> EmptyHost
```

This failed silently in the worst way: the inbound request still answered 204, so metadata looked healthy,
while every follow-up fetch built from that string died in the HTTP client and the remote content simply
never arrived. Audit every `format!("http://{}:{}", ip, port)` before widening a bind, and unwrap
v4-mapped addresses (`::ffff:a.b.c.d`) first so they render dotted rather than bracketed.

Also check any allow-list is v6-aware: a v4-only CIDR test silently rejects a v6 peer, and a peer dialled
by MagicDNS name can arrive over either family.

## Constant-time token comparison without a dependency

`subtle` and `ring` expose vetted constant-time equality, but their slice comparisons take equal-length
inputs — a length mismatch is resolved before the constant-time part, which leaves exactly the leak you
were removing if attacker-controlled length reaches it. Folding length into the accumulator is a few lines
and avoids the dependency:

```rust
fn tokens_match(a: &[u8], b: &[u8]) -> bool {
    let mut diff = (a.len() ^ b.len()) as u8;
    for i in 0..a.len().max(b.len()) {
        diff |= a.get(i).copied().unwrap_or(0) ^ b.get(i).copied().unwrap_or(0);
    }
    diff == 0
}
```

Keep the threat honest: over a LAN or tailnet the timing noise floor is high, so this closes a real class
of bug rather than a likely attack. It does **not** bound the guessing budget — a constant-time compare
still lets an attacker try tokens as fast as the socket accepts them, so token length and a failed-auth
delay are separate questions.

## Knowing *which* peer called: `tailscale whois`, not the token

The source check above answers "is this caller on the tailnet". It does not answer "which machine is
this", and a shared bearer token cannot either: one secret across a fleet proves *a token-holder*, not a
machine. So any field the sender uses to name itself — a `device_name` in the request body, an
`origin_device` — is a **claim**, and if that field decides whose data the request becomes, any
token-holder can attribute their push to your laptop.

The authentication you need already happened. The listener is tailnet-scoped, so a packet only arrives
because WireGuard authenticated the node behind it — the mistake is discarding that result and reading a
self-declared string instead. `tailscale whois` hands it back, from the local daemon:

```
$ tailscale whois --json 100.86.97.31:9078
Node.ComputedName : chrome            # short node name
Node.Name         : chrome.tail3e8704.ts.net.
UserProfile       : someone@example.com   # the tailnet user owning the node
```

It fails closed on everything that is not a tailnet peer, which is what makes it usable as a gate:

```
$ tailscale whois 8.8.8.8:443     -> peer not found (exit 1)
$ tailscale whois 127.0.0.1:9078  -> peer not found (exit 1)
```

Note the loopback result: a localhost test harness is **not** a tailnet peer, so it degrades to
"unattested" rather than being refused. Design for that, or your own tests fail closed.

### The binding must be receiver-local, or the check is circular

whois gives you a *tailnet node name*. What you are checking is a name in *your* namespace. Those are
usually not equal — one real pair was `device_name = "CHROME"` against node `chrome`, and
`device_name = "Olegs-MacBook-Air.local"` against node `air`. So you need a map, and **it cannot ride the
wire**: a sender controls every field of its own request, so a hostile node would simply send its own
truthful node name beside the claimed device name and attest itself. An out-of-band binding in the
receiver's config is what makes the check non-circular.

Three outcomes, and only one refuses:

| outcome | when | action |
|---|---|---|
| attested | a binding exists and the source is that node | accept |
| claimed | no binding configured, or no answer from whois | accept, and *say* it was unchecked |
| mismatch | a binding exists and the source is a different node | refuse |

Defaulting the unbound case to `claimed` rather than `mismatch` is what lets this ship into a running
fleet without breaking every deployment that has not written a map yet.

### Practical notes

- **Locate the binary explicitly.** A GUI app inherits no shell PATH; on macOS the CLI lives inside the
  app bundle at `/Applications/Tailscale.app/Contents/MacOS/Tailscale`, on Windows at
  `C:\Program Files\Tailscale\tailscale.exe`.
- **Give the subprocess a timeout.** Rust's `Command` has none; poll `try_wait` to a deadline and `kill`,
  or a wedged daemon holds a blocking thread forever.
- **Cache per source address** (~60 s). The address→node binding is stable for a node's lifetime; the
  cache is about bounding subprocess spawns.
- **Store the verdict at ingest, do not recompute it on read.** It is a fact about *a connection that
  happened* — the address it arrived from — and the read path does not have that address.
- **Report it.** An attestation that silently succeeds is indistinguishable from one that silently
  no-ops. Surface `attested`/`claimed` per peer so the check's absence is visible.

### Why not per-device tokens

The obvious alternative — a token per peer instead of one fleet-wide — does work and is better than a
shared secret. It is still the weaker option: it is a bearer secret, so reading one machine's config
impersonates it completely; rotation touches every machine; and it reimplements, with new failure modes,
an identity Tailscale is already asserting underneath you. Reach for it only if the fleet might leave the
tailnet.

**Do not call the result "verified".** It is as good as the tailnet's ACLs and the fleet token not having
leaked. And identity is not intent: it says the request really came from that node, never that whatever
is running there is behaving.
