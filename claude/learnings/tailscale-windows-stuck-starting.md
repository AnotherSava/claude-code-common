# Tailscale on Windows stuck in "Starting…" with "unreachable network"

Seen 2026-11-22 on a Windows desktop with both Ethernet and Wi-Fi up. The tray sat on "Starting…" after a restart, and `tailscale status` printed `unexpected state: NoState` with this health line:

```
You are logged out. The last login error was: fetch control key: Get "https://controlplane.tailscale.com/key?v=148": dial tcp [2606:...]:443: connectex: A socket operation was attempted to an unreachable network.
```

The IPv6 address in that error points away from the cause. The machine had no IPv6 route at all, so the IPv6 attempt fails instantly whatever is wrong; the IPv4 attempt was the one that mattered, and it was hanging.

## What it was

The Ethernet adapter reported a 1 Gbps link but could not reach the router: its ARP entry for the gateway stayed `Incomplete` and pings sourced from its address timed out. The adapter's event log showed a link drop and reconnect shortly before. Windows routed ordinary traffic over Wi-Fi, so the browser and everything else kept working, but tailscaled's control and DERP connections all left from the Ethernet address and sat in `SynSent`.

## How to tell, without admin rights

Test each interface separately; a plain `curl` follows the system route and succeeds, which is what hides the problem.

```bash
for ip in <ethernet-ip> <wifi-ip>; do
  curl -4 -s -o /dev/null -m 6 --interface $ip -w "$ip: %{http_code}\n" https://controlplane.tailscale.com/key?v=148 || echo "$ip FAILED"
done
```

Then, in PowerShell: `Get-NetNeighbor -IPAddress <gateway>` (an `Incomplete` state on one adapter is the tell) and `Get-NetTCPConnection -State SynSent` filtered to the tailscaled process, whose local address names the interface it is stuck on.

## Fix

Reseat the cable or restart the adapter from an elevated PowerShell (`Restart-NetAdapter -Name "<adapter>"`). Disabling the dead adapter also works: tailscaled then binds to the working one. Restarting Tailscale alone does not help, since it picks the same interface again.
