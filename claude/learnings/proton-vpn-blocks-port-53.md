# Proton VPN on Windows blocks port 53 machine-wide, breaking Tailscale split DNS

Measured 2026-09-14 on Windows 11 with Proton VPN 5.1.7 (WireGuard) and Tailscale 1.98.10. The user had
split tunnelling in **inverse/include** mode with exactly one app (a torrent client) in the list, expecting
everything else to be untouched. Tailnet hostnames served by a peer's DNS resolver stopped resolving
whenever Proton was connected, while the tailnet data plane stayed perfectly healthy.

## Include-mode split tunnelling makes this worse, not better

The counter-intuitive part, from `src/ProtonVPN.Service/KillSwitch/KillSwitch.cs` in `ProtonVPN/win-app`:

```csharp
bool dnsLeakOnly = _serviceSettings.SplitTunnelSettings.Mode == SplitTunnelModeIpcEntity.Permit
                   && state.Status == VpnStatus.Connected;
```

`Permit` is inverse/include mode, so putting **anything** in the include list sets `dnsLeakOnly = true`.
`Firewall.ApplyFilters` then calls `EnableDnsLeakProtection` unconditionally but skips
`EnableBaseLeakProtection` — and `PermitFromProcesses`, the only app-scoped permit Proton has, lives *inside*
the branch that got skipped. An empty include list would at least keep that permit list; an include list
removes it. Either way the permit list only ever covered Proton's own client, service and WireGuard service,
never a third-party resolver.

There is no setting that disables DNS leak protection. Proton documents it as unconditional and states
outright that Pi-hole is incompatible for the same reason.

## What actually gets installed

`BlockDns(3, …)` creates four filters — remote UDP 53 v4, TCP 53 v4, UDP 53 v6, TCP 53 v6 — each
`Action.HardBlock` at weight 3 on `FWPM_LAYER_ALE_AUTH_CONNECT_V4/V6`, **with no application condition and
no remote-address condition**. The only counterweight is `PermitFromNetworkInterface(4, …)`, a weight-4
`SoftPermit` keyed to the Proton tunnel's interface index.

Alongside it, an NRPT rule with `Name = ["."]`, `GenericDNSServers = <tunnel resolver, e.g. 10.2.0.1>`,
`DisplayName = "Proton VPN"`, `Comment = "Force all DNS requests via Proton VPN"`. That rule is what keeps
the machine working: every Windows DNS Client query is redirected to the in-tunnel resolver and egresses on
the one permitted interface.

With `KillSwitchMode = Off` the filters are `SessionType.Dynamic` and are torn down at disconnect, with the
service still running. Proton's *advanced* kill switch makes them `Permanent` and boot-persistent —
deliberately, and documented as such.

## Diagnosing it without elevation

`netsh wfp show filters` needs an elevated token, so use the socket-level signature instead. It is
unmistakable:

| probe | result |
|---|---|
| TCP connect to any `<ip>:53` | `WSAEACCES` / native **10013**, instantly |
| UDP send to any `<ip>:53` | send succeeds, reply never arrives (silent drop) |
| TCP `<ip>:443`, UDP `<ip>:123` | unaffected |

**Do not test with `Resolve-DnsName` — it will tell you the port is fine.** `DnsQueryEx` goes through the
DNS Client service, and that is precisely the one path still working, so a `-Server 8.8.8.8` lookup
"succeeds" while every other process on the machine is blocked. Worse, the answer is not even from the
server you named: the `.` NRPT rule redirects it to the tunnel resolver, which is why two different
`-Server` values return identical answers. Use a raw socket from Python or a `TcpClient`/`UdpClient` in
PowerShell. Same trap as [[windows-firewall-wfp-diagnosis]]: the tool that looks authoritative is reading a
different layer than the one enforcing.

The A/B is one click and settles ownership in seconds — probe, disconnect the VPN, probe again. No need to
exit the client or stop its service.

## What this breaks in Tailscale, and what it does not

- **Not the data plane.** Peers stay `direct`, no drop to DERP, no relay. The WireGuard transport is UDP on
  its own port and matches nothing.
- **Not routing.** Proton's default route sits at metric 32000 and loses to the physical NIC, and it claims
  no part of `100.64.0.0/10`. A `route print` glance can miss the tunnel adapter entirely because of that
  metric.
- **Not NRPT contention.** `StaticNrptInvoker.CheckAndDeleteRule` deletes only keys whose `DisplayName` is
  `Proton VPN` or whose `Comment` is `Force all DNS requests via Proton VPN`. Tailscale's keys carry neither
  value, so they are never touched, reordered or rewritten. Longest-suffix match also means Tailscale's
  specific rules keep beating Proton's `.`.
- **Names inside your own tailnet keep resolving** — `tailscaled` answers those from its netmap with no
  upstream query.
- **What dies is every lookup `tailscaled` must forward.** Split-DNS zones pointed at a peer's resolver, and
  `*.ts.net` names outside your own tailnet (that split route targets Tailscale's public `ts.net`
  authoritative server on port 53). `net/dns/resolver/forwarder.go` sends upstream queries from tailscaled's
  own `ListenPacket(":0")` socket, so tailscaled is a victim of the block, not an author of it.

Tailscale cannot be the blocker, on source: `net/dns/manager_windows.go` only writes NRPT rules and
interface DNS, its netsh rules are inbound `allow` only, and its one WFP mechanism (`wf/firewall.go`) is an
exit-node killswitch that runs in a `Dynamic` session and contains `permitDNS`, which *permits* remote 53
for every application.

## Remedies, in the order worth trying

1. **Pin the affected hostnames in the hosts file.** Measured to work with the VPN connected: the resolver
   loads hosts entries into its cache with no query at all, so port 53 is never involved. On Windows the
   entries must go **above** Tailscale's `# TailscaleHostsSectionStart` marker, not inside its managed
   block. Cost: static — the entries need editing if a peer's tailnet IP ever changes, and they shadow
   MagicDNS for those names on any machine you copy them to.
2. **Move the split-DNS resolver off port 53.** Every Proton filter conditions on port 53, so a resolver on
   another port matches nothing. `types/dnstype/dnstype.go` parses `Resolver.Addr` with
   `netip.ParseAddrPort`, but its comment marks `IP:port` as "for tests" — unverified whether a tailnet's
   admin console accepts the form, and the change is tailnet-wide, so every other device starts querying the
   odd port too. Self-hosted DoH is not a substitute: it needs `BootstrapResolution`, recorded as "not yet
   used".
3. **Just disconnect the VPN** when you need those names. With one app in the include list, that costs one
   app's tunnel.

Ruled out, with reasons: Proton's **custom DNS servers** only select which server the tunnel and the NRPT
rule point at, and are referenced by neither `Firewall.cs` nor `KillSwitch.cs`. Proton's **"Access devices
by name"** toggle switches enforcement from NRPT to a callout conditioned on
`FWPM_CONDITION_INTERFACE_INDEX != <tunnel ifIndex>`, so a query leaving on any other interface is still
killed — just with a synthesized SERVFAIL instead of a timeout, and TCP 53 and IPv6 stay hard-blocked.
**Adding the resolver process to the split tunnel** does nothing, because those filters are bind/connect
*redirect* only, with no permits. **`tailscale set --accept-dns=false`** is a blanket opt-out that takes
MagicDNS, split DNS and search domains together.

## Trap: never run `ProtonVPN.NrptWatchdog.exe --force` while connected

`C:\Program Files\Proton\VPN\v<version>\ProtonVPN.NrptWatchdog.exe --force` deletes Proton's NRPT rules by
marker, and while connected that includes the live `.` rule — the only reason the Windows DNS Client can
resolve anything at all. Every name resolution on the machine stops the instant it runs. The service then
recreates the rule, so a follow-up `Get-DnsClientNrptPolicy -Effective` still shows it and the command looks
like it failed. Run it only with the client **exited**, not merely disconnected. Its heavier sibling,
`ProtonVPN.RestoreInternet.exe`, calls `RemoveWfpObjects(0)` and then deletes the rule; neither tool appears
in Proton's published documentation.

A disconnect can also leave an orphaned `.` rule behind pointing at the now-dead tunnel resolver. It is
usually harmless — Windows falls back to the interface's own nameservers — but `tailscale dns status` will
report the dead address as the system nameserver, which is misleading when reading it later.

## Upstream

- `tailscale/tailscale#20637` — the same conflict, filed against Proton 5.1.5 on Windows, open.
- `safing/portmaster#1246` — includes a `netsh wfp` dump naming the filters: "ProtonVPN DNS filter / Block
  UDP 53 port" at `FWPM_LAYER_ALE_AUTH_CONNECT_V4`, and a callout that "sends server failure packet response
  for non TAP/TUN DNS queries".
- `ProtonVPN/win-app` has GitHub issues **disabled**, so there is no vendor tracker to file against.
- The same technique appears in other products (`OpenVPN --block-outside-dns` produces the identical 10013),
  so the diagnosis above transfers.
