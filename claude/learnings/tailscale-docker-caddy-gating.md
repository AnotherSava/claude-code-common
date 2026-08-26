# Gating a Dockerized web service to Tailscale-only (Caddy)

How to make an admin panel / internal dashboard reachable **only over Tailscale** while the same box keeps serving public traffic, when the app runs in Docker behind Caddy. Learned building this for a Next.js app on a Netcup box (Caddy in Docker, ports 80/443 published).

## The gate: Caddy `remote_ip` on the Tailscale CGNAT range

Tailscale's whole address space is `100.64.0.0/10` (plus IPv6 `fd7a:115c:a1e0::/48`). Because Caddy is the internet edge (nothing proxies in front of it), `remote_ip` is the true TCP peer and **cannot be spoofed** — do NOT use `client_ip` (that reads the attacker-controlled `X-Forwarded-For`).

```caddyfile
admin.example.com {
	@offnet not remote_ip 100.64.0.0/10 fd7a:115c:a1e0::/48
	respond @offnet 404
	reverse_proxy app:3000
}
```

Off-tailnet → 404 (use 404, not 403 — doesn't disclose the panel exists). Tailnet-sourced → proxied. To block a path on the *public* host too: `@admin path /admin /admin/*` → `respond @admin 404`.

## THE landmine: Tailscale SNATs the source to the Docker bridge IP

If Tailscale was installed/started **after** Docker, a tailnet peer hitting the host's tailnet IP on a published port arrives at the container with source `172.17.0.1` (the docker0 gateway), not the real `100.x`. The `remote_ip` gate then 404s the operator too. Root cause (tailscale/tailscale#10205, #13754): Docker's DNAT forwards `tailscale0 → docker0`, tailscaled marks the forwarded packet with `0x40000`, and with the default `--snat-subnet-routes=true` the rule `-A ts-postrouting -m mark --mark 0x40000/0xff0000 -j MASQUERADE` SNATs it. Public traffic arrives on `eth0`, is never marked, so it's fine — which is why the app's own rate-limiter (keyed on real client IP) works but the tailnet gate doesn't.

**Fix (zero-downtime, reboot-safe):**
```
sudo tailscale set --snat-subnet-routes=false
```
`tailscale set` reprograms netfilter in place — no daemon restart, no dropped tailnet session, Docker/containers untouched. Safe on a plain web host (not a subnet router). It removes the `ts-postrouting … MASQUERADE` rule and persists in prefs. **Do NOT** `docker restart` (bounces every container = site outage) or `systemctl restart tailscaled` (leaves the ordering wrong, several report it doesn't fix it).

**There is no Caddy-side recovery** — it's an L3 SNAT with no forwarded header carrying the real IP. Must be fixed at the network layer.

**Verify (read-only):** `sudo iptables -t nat -S ts-postrouting` — the MASQUERADE line is gone after the fix. Or, since Caddy access logging is usually off, temporarily `respond "{remote_host}"` to echo what Caddy sees (`172.x` = still broken, `100.x` = fixed). A self-test from the box to its own tailnet IP is treated as a tailnet source and is a fair proxy: `curl --resolve name:443:<box-tailnet-ip> https://name/`.

## Real cert for a tailnet-only hostname (no public DNS record) → DNS-01

If the hostname has **no public A record** (maximal isolation), Let's Encrypt HTTP-01/TLS-ALPN can't validate it (nothing public to reach). Use **DNS-01**, which stock Caddy can't do — build a custom image with the DNS-provider module:

```dockerfile
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/porkbun
FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```
```caddyfile
tls {
	dns porkbun {
		api_key {env.PORKBUN_API_KEY}
		api_secret_key {env.PORKBUN_SECRET_KEY}
	}
}
```
(Directive names per provider README — porkbun is `api_key` / `api_secret_key`.) The box now holds a broad DNS API key — acceptable if it already holds the DB/secrets, but weigh it. Alternatives: `tls internal` (self-signed, install Caddy's root CA per device) or a `*.ts.net` name with a Tailscale-provisioned cert. Even without a public record, keep the `remote_ip` gate — Caddy still listens for that SNI on the public 443, so a direct-IP + SNI hit would otherwise reach it.

## Making the tailnet-only name resolve on all devices (incl. phone)

Hosted Tailscale has **no native custom DNS records** (MagicDNS only auto-registers `device.tailnet.ts.net`; the `ExtraRecords` field exists in the protocol but only Headscale exposes it — issue #1543). So use **split-DNS**: run a tiny resolver on the box (already a tailnet node) that answers the private names and forwards the rest, then point a Tailscale "restricted nameserver" at it.

dnsmasq container, bound to the tailnet IP only (never a public open resolver):
```
# dnsmasq.conf
no-resolv
no-hosts
address=/admin.example.com/100.x.y.z
address=/analytics.example.com/100.x.y.z
server=1.1.1.1
server=9.9.9.9
```
```yaml
# compose: bind to the tailnet IP, not 0.0.0.0
ports: ["100.x.y.z:53:53/udp", "100.x.y.z:53:53/tcp"]
```
Then admin console → DNS → Nameservers → **Custom `100.x.y.z`, Restrict to search domain `admin.example.com`** (add a second one for the other subdomain — two narrow restrictions leave the apex/www/MX on public DNS). Phone: enable **"Use Tailscale DNS"** in the app; Android: system Private DNS → Automatic/Off. Split-DNS (not a public A record → 100.x) is what makes it work on a phone — a public 100.x answer gets stripped by DNS-rebinding protection, but a MagicDNS-served answer doesn't traverse the phone's upstream. Per-device `/etc/hosts` is the zero-infra fallback.

## Same hostname vs. a separate admin hostname

Two ways to gate `/admin`:
- **Same hostname** (`example.com/admin` gated by `remote_ip`): needs the operator's devices to resolve the *whole* `example.com` to the tailnet IP — which then **masks the public path** (you never see the site as a real customer does). Bad for dogfooding.
- **Separate hostname** (`admin.example.com`, tailnet-only): the public site stays 100% public and normally-browsed. This works with **zero app changes** *iff* the admin session cookie is **host-only** (no `Domain=`) and redirects are **relative** (`redirect("/admin")`, not `APP_BASE_URL`-absolute) — verify both in the app before assuming. If the app hardcodes an absolute base URL for admin or a domain-scoped cookie, a separate hostname breaks login. Prefer the separate hostname; check the cookie/redirect assumptions first.

The `/admin` path prefix stays load-bearing even with a dedicated host: it's one app serving both customer and admin routes, so the prefix is the namespace the proxy gates on. Don't try to strip it — the app's own nav links and redirects assume it.

### The gate is worthless without a resolution path to the tailnet IP

A `remote_ip 100.64.0.0/10` matcher only fires when the request genuinely **arrives over the tunnel**. Tailscale
routes only traffic addressed to 100.64/10; a browser resolving your hostname to the box's **public** A record
goes out over the ordinary internet, so the source is the operator's public IP and the gate 404s *them* along with
everyone else. Writing the matcher is the easy half — the half that's easy to forget is making the name resolve to
`100.x` on operator devices (split-DNS via dnsmasq, or no public record at all).

That is the real reason the separate-hostname option above wins. It is not merely tidier: with one hostname you
must choose between the public path and the gated one, because a name resolves to exactly one address per device.
Point it at the tailnet and you can never see your own site as a visitor does; point it at the public IP and the
gate never matches. A site whose *whole point* is being publicly browsable cannot use same-host path gating.

Cost to budget for: the tailnet-only hostname has no public record, so its cert must come from **DNS-01** — which
means the Caddy image needs the plugin for *that zone's* DNS provider. Two domains on two providers means two
plugins in the same `xcaddy` build; a Porkbun-only build cannot issue for a Cloudflare-hosted name.

### Windows: the NRPT rule is a *suffix* match, so the bare hostname isn't routed

A split-DNS route can be correct on the Tailscale side and still not reach the browser. On Windows the client
implements it as an NRPT (Name Resolution Policy Table) rule, and it registers the namespace with a **leading
dot**:

```powershell
(Get-DnsClientNrptRule).Namespace   # -> .whats-next.example.com
```

A leading-dot namespace is a DNS *suffix* rule: it matches `anything.whats-next.example.com` but **not
`whats-next.example.com` itself**. So a gate keyed on the source being `100.x` keeps refusing the operator, on a
machine where everything looks configured.

What makes it confusing is that Tailscale's own resolver is fine — only the OS isn't pointed at it:

```
tailscale dns query whats-next.example.com   # Forwarding to resolver: 100.x.y.z -> RCodeSuccess
nslookup whats-next.example.com 100.x.y.z    # correct tailnet answer
nslookup whats-next.example.com              # the PUBLIC address
```

So diagnose in that order — resolver first, then the OS. `ipconfig /flushdns` does not help; the rule never
matched. Tailscale's docs offer per-device hosts entries as the supported fallback, and that is the quickest way
to unblock one machine:

**The inverse trap, once split-DNS *is* working: your own workstation cannot tell you what the public record
says.** On a tailnet-connected machine a plain `dig name` returns the split answer — the `100.x` address — so
it is easy to conclude that the public A record points at a tailnet IP (and to start "explaining" how the
public cert was ever issued for it). Always check a public record against a resolver outside the tailnet:

```
dig +short name.example.com               # split-DNS answer: 100.x.y.z
dig +short @1.1.1.1 name.example.com      # what the world actually sees
```

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "100.x.y.z name.example.com"
```

TLS still validates — the same proxy serves the same certificate on the tailnet interface.

## Giving a tailnet service a real https origin (`tailscale serve`)

The sections above gate a *public* hostname to tailnet sources. The opposite problem — a plain-HTTP service on a
private address that an https page must load from — has a one-command answer, and it needs no DNS record and no
DNS-01 dance:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8096   # undo: tailscale serve --https=443 off
```

The service is then `https://<node>.<tailnet>.ts.net` with a real Let's Encrypt certificate, reachable by every
tailnet device. That is what unblocks fetching from it inside an https page, where mixed-content rules refuse
`http://192.168.x.x` outright.

**HTTPS certificates must be enabled for the tailnet first**, and this is togglable by API even though the docs
present it as an admin-console switch:

```bash
curl -u "$TAILSCALE_API_KEY:" https://api.tailscale.com/api/v2/tailnet/-/settings          # → {"httpsEnabled": false, …}
curl -X PATCH -u "$TAILSCALE_API_KEY:" -H 'Content-Type: application/json' \
     -d '{"httpsEnabled": true}' https://api.tailscale.com/api/v2/tailnet/-/settings       # → 200, body `null`
```

Side effect worth naming before flipping it: the tailnet name and every node you request a certificate for are
published to the public Certificate Transparency logs.

**MagicDNS names do not resolve off-tailnet.** `nslookup <node>.<tailnet>.ts.net 8.8.8.8` returns no address. That
is a useful property: a client that wrongly believes it is on the tailnet fails at DNS in milliseconds rather than
hanging on a TCP connect to an unroutable 100.x address, so "guess, then fall back" is a viable strategy.

## Gating inside the app instead of at the proxy

When the *application* (not Caddy) has to decide whether a request came over the tailnet, it reads
`X-Forwarded-For` — and there is one trap that makes this silently never fire in development:

**Next.js's dev server sets `x-forwarded-for: ::ffff:127.0.0.1` itself.** So code that reads the *last* entry (the
usual "the value my own proxy appended" reasoning) gets loopback on every local request, concludes "not tailnet",
and the feature never engages while you develop it. Read the **first** entry instead — the original client, which
is the standard reading of the header and the only one that survives more than one hop.

```js
const TAILNET_V4 = /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./;   // 100.64.0.0/10 — NOT /^100\./
const TAILNET_V6 = /^fd7a:115c:a1e0:/i;
const LOOPBACK   = /^(127\.|::1$|::ffff:127\.)/;                  // dev: browser is on the app's own machine
const [first] = (headers().get("x-forwarded-for") ?? "").split(",");
```

`100.64.0.0/10` is `100.64.x` – `100.127.x`. A lazy `/^100\./` also matches `100.63.…` and `100.200.…`, which are
ordinary public space. Accepting loopback alongside it is what makes the same code path testable in development.

Spoofing the first entry is trivial, so this must not be the only thing protecting anything — pair it with real
authentication and treat the address purely as a routing hint.
