# Remote Login on macOS, reachable on the tailnet and nowhere else

Turning on macOS Remote Login and confining port 22 to a Tailscale interface. The Windows half of the
same job is in `windows-openssh-over-tailscale.md`, and the two are not symmetrical — almost nothing
transfers. Coordinates for the actual hosts are in `[[machines-private]]`; everything here is
platform mechanics.

A laptop is the case that makes this worth doing. A desktop that never leaves the house is behind one
router; a laptop joins hotel and café networks, where an open port 22 is exposed to strangers on the
same segment.

## `ListenAddress` is never consulted — pf is the only lever

macOS runs sshd through **launchd socket activation**: `/System/Library/LaunchDaemons/ssh.plist`
invokes `sshd -i`, and launchd owns the listening socket, accepts the connection, and hands the
already-connected descriptor over. sshd never calls `bind()`, so `ListenAddress` and `Port` in
`sshd_config` are read by nobody. The same is true on systemd with `ssh.socket` enabled.

Editing the plist is SIP-protected, and running your own `sshd -D` means maintaining a parallel
service. The packet filter is the supported lever.

That is also a *feature* here: `tailnet-scoped-service-binding.md` records that binding a socket to a
tailnet address introduces a startup race (the VPN is not up at login) and a socket that outlives its
address. A pf rule has neither problem, because it is evaluated per packet rather than once at bind.

## Tailscale SSH is not an option on a GUI-variant Mac

The Tailscale SSH *server* needs the open-source `tailscale`/`tailscaled` build. The App Store and
standalone (macsys) variants cannot host it, and a Mac normally runs one of those — check
`CFBundleIdentifier` (`io.tailscale.ipn.macsys` is the standalone GUI). The failure is quiet:
`sshHostKeys` is null in `tailscale status --json`, which reads identically to "enabled but not
configured".

## The interface-group trap: `pfctl -vnf` proves syntax, not selection

pf matches a name with no trailing digit as an interface **group**, so `on utun` looks like the way to
follow Tailscale across reboots when it comes back as `utun9` instead of `utun8`. On macOS it parses
and matches nothing.

```
pass in quick on utun inet proto tcp from any to <tailnet-ip> port 22 flags S/SA keep state
block drop in quick proto tcp to any port 22
```

Measured: sshd listening, the anchor loaded, the address unchanged — and both the tailnet *and* the LAN
refused, because the pass rule selected no interface and every packet fell to the block. A rule that
matches nothing fails **closed**, which is the safe direction and also the confusing one: it looks
exactly like scoping that is working too well.

`pfctl -vnf <file>` accepting the rule is what makes this easy to ship. It proves the rule is
well-formed and says nothing about whether it selects an interface. The query that answers that:

```
pfctl -s Interfaces -i utun     # empty list = the group resolves to nothing
pfctl -a <anchor> -s rules -v   # Evaluations/Packets per rule = which one actually matched
```

Read the counters before believing any pf rule. They are the only instrument that distinguishes
"matched and passed" from "never matched".

## Match the destination address instead

The node's tailnet address is stable across reboots and needs no interface name:

```
pass in quick on lo0 proto tcp to any port 22 flags S/SA keep state
pass in quick inet proto tcp from any to <tailnet-ip> port 22 flags S/SA keep state
block drop in quick proto tcp to any port 22
```

Three things about that ruleset:

- **Destination, not source.** A source-CIDR rule (`from 100.64.0.0/10`) is forgeable by anyone on the
  same LAN, and `tailnet-scoped-service-binding.md` records why that CIDR proves nothing anyway —
  several ISPs hand out `100.64/10` directly. A packet legitimately carrying the node's own tailnet
  address as its *destination* arrived over WireGuard.
- **The loopback rule is required.** The block matches on destination port alone, so without it
  `127.0.0.1:22` is cut for everything local.
- **What it does not cover:** someone already on the same layer-2 segment who knows the node's tailnet
  address can address a frame to its MAC with that destination IP, and macOS's weak host model accepts
  it. Closing that means naming the physical interfaces, which is the brittleness the group trap above
  was an attempt to avoid. Key-only auth is what stands behind it.

## Nothing loads pf at boot

Unlike FreeBSD, macOS does not read `/etc/pf.conf` at startup and leaves pf disabled; each component
enables it with `pfctl -E` and releases with `-X`, reference-counted. So the anchor needs a
LaunchDaemon running `pfctl -E -f /etc/pf.conf` with `RunAtLoad`, or it is live only until the
next restart.

Add the anchor through `/etc/pf.conf` with both lines — `anchor "<name>"` *and*
`load anchor "<name>" from "/etc/pf.anchors/<name>"`. A macOS update rewrites `/etc/pf.conf`, so keep
the installer idempotent and treat re-running it as the repair rather than a fresh install.

## `systemsetup -setremotelogin` needs Full Disk Access; launchctl does not

`systemsetup -f -setremotelogin on` writes a TCC-protected preference, so from an ordinary terminal it
fails — and the failure is easy to miss in a script's output, leaving an install that looks complete
with nothing listening. Verified on macOS 26.5:

```bash
launchctl enable system/com.openssh.sshd
launchctl bootstrap system /System/Library/LaunchDaemons/ssh.plist
```

`launchctl bootstrap` returning "already bootstrapped" is success, not failure. The GUI switch
(System Settings > General > Sharing > Remote Login) is the other route and is the one the Settings
pane reflects.

Order the install so the firewall goes in **before** sshd starts, or port 22 is briefly open on
whatever network the machine is sitting on.

## Password auth is on by default — a drop-in turns it off

Stock macOS sets no `PasswordAuthentication` anywhere, so OpenSSH's default (`yes`) applies the moment
Remote Login is enabled. `/etc/ssh/sshd_config` carries `Include /etc/ssh/sshd_config.d/*` near the
top and sshd takes the **first** value for a keyword, so a drop-in there beats the main file. macOS
ships `100-macos.conf`; number yours above it.

## Verifying it: a local probe cannot

A connection from the machine to its own LAN address is routed over `lo0`, which the anchor passes, so
a local `nc` reports the port open however the rule behaves on the physical interface. The test has to
be dialled from another host, and it needs **both** legs or the result is unreadable:

| tailnet | LAN | meaning |
|---|---|---|
| True | False | scoped correctly |
| True | True | sshd is up, the rule is not working |
| False | False | **sshd is not running** — says nothing about the firewall |

That last row is the one that wastes time: it looks like successful scoping and is not.
