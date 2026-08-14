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
