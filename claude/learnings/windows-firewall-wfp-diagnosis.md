# Diagnosing a dark port on Windows: read the WFP drop, don't reason about the rules

Measured 2026-09-06 on a Windows 11 box where Jellyfin's TCP 8096 had been silently dropped for a day
while an enabled, correctly-addressed Allow rule sat right there covering it. Every conventional check
said the port should be open. The packet-level record said otherwise and named the exact filter in about
two minutes.

## The rules list is not the enforcement

`Get-NetFirewallRule` tells you a rule exists, is Enabled, has Action=Allow and `PrimaryStatus OK`. None
of that means it **matches**. Each rule compiles down to one or more WFP filters carrying conditions, and
a condition that stops matching takes the rule out of play while every PowerShell readout keeps looking
healthy.

The real case: Tailscale's blanket `Tailscale-In` compiled to a filter conditioned on

```
IP_LOCAL_ADDRESS    = 100.x.y.z      (matched)
ORIGINAL_PROFILE_ID = 2  (Private)
CURRENT_PROFILE_ID  = 2  (Private)
```

while `Get-NetConnectionProfile` and `netsh advfirewall monitor show currentprofile` both reported that
adapter's network as **Private**. One of the profile conditions was nonetheless failing. Rules that
carried `-Profile Any` on the same interface (sshd, Plex, RDP) kept working throughout; everything whose
only cover was the profile-scoped rule went dark together. That asymmetry is the tell.

## Never infer a firewall drop from a hang

A TCP connect that times out rather than being refused reads like a DROP, and on Windows it proves
nothing: the default inbound action is Block, so a port with **no listener at all** also times out with
no RST. A closed port and a filtered port are indistinguishable from outside. Get the drop record instead.

## Net-event collection is often already on, so this is read-only

Check before reaching for `auditpol`, which would be a mutation:

```
netsh wfp show options optionsfor=netevents      # -> "netevents = on" on a default install
```

When it is on, WFP is already recording classify-drops in a ring buffer. Provoke the failure, then dump:

```powershell
$f = Join-Path $env:TEMP 'wfpev.xml'
netsh wfp show netevents file=$f | Out-Null
$x = [xml](Get-Content $f)
$x.netEvents.item |
  Where-Object { $_.header.ipProtocol -eq '6' -and $_.header.localPort -eq '8096' } |
  Select-Object -Last 3 |
  ForEach-Object {
    [PSCustomObject]@{
      T = $_.header.timeStamp
      Loc = "$($_.header.localAddrV4):$($_.header.localPort)"
      Rem = "$($_.header.remoteAddrV4):$($_.header.remotePort)"
      FilterId = $_.classifyDrop.filterId
      Layer = $_.classifyDrop.layerId
    }
  }
```

`header.appId.data` is the owning executable as **UTF-16LE hex** (`\device\harddiskvolumeN\...`), which
is how you confirm the drop belongs to the process you care about rather than something else on the port.

Then resolve the filter id against the filter dump:

```powershell
$f = Join-Path $env:TEMP 'wfpdiag.xml'
netsh wfp show filters file=$f | Out-Null
([xml](Get-Content $f)).wfpdiag.filters.item |
  Where-Object { $_.filterId -eq '137207' } |
  Select-Object filterId, @{n='Name';e={$_.displayData.name}}, layerKey, subLayerKey,
                @{n='Act';e={$_.action.type}}, @{n='W';e={$_.effectiveWeight.uint64}}
```

Both files land in `%TEMP%`; delete them afterwards. The filter dump is ~10 MB and ~4000 filters.

## Reading the answer

- **`Query User`** is Windows' default-deny filter: *"blocks any inbound packets for which there is no
  explicit rule to allow the packet."* If it won, nothing allowed the packet. That is a complete answer,
  and it points at the allow rule you expected to match rather than at some mysterious blocker.
- **Arbitration is per-sublayer.** Within `FWPM_SUBLAYER_MPSSVC_WF` the highest `effectiveWeight` wins,
  but a BLOCK winning in *any other* sublayer still blocks the packet. So enumerate blocks per sublayer,
  not just the globally-highest weight:
  - `MPSSVC_WF` — ordinary firewall rules, plus `Query User`
  - `MPSSVC_WSH` — Windows Service Hardening, with its own `WSH Default Inbound Block`
  - `MPSSVC_QUARANTINE` — blocks all inbound on an interface until an `Interface Un-quarantine filter`
    matching that interface LUID **and the current `INTERFACE_QUARANTINE_EPOCH`** permits it
  - `MPSSVC_APP_ISOLATION` — AppContainer/UWP
- Inbound TCP accept is `FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4` (layerId 44). Listening is a separate layer,
  `ALE_AUTH_LISTEN_V4`, so a socket can be allowed to bind and still be refused inbound connections.

## Check every policy store, not just the default

`Get-NetFirewallRule` with no `-PolicyStore` reads the **PersistentStore**. What is enforced is the
**ActiveStore**, and a rule can exist in one and not the other:

```powershell
Get-NetFirewallRule -PolicyStore ActiveStore -DisplayName 'Tailscale*'
Get-NetFirewallRule -PolicyStore ActiveStore |
  Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' }
```

Also worth knowing: `Get-NetFirewallProfile -Name Private | Select AllowLocalFirewallRules` returning
`NotConfigured` means locally-created rules are honoured; a GPO setting it to False would make every
locally-added rule inert while leaving it visible and Enabled.

## The fix shape that survives

When a profile-conditioned rule stops matching for reasons you cannot explain, do not try to revive it.
Add a dedicated rule that does not depend on the failing condition:

```powershell
New-NetFirewallRule -DisplayName 'Jellyfin (tailnet)' -Direction Inbound -Action Allow `
  -Protocol TCP -LocalPort 8096 -InterfaceAlias Tailscale -Profile Any `
  -Program 'C:\Program Files\Jellyfin\Server\jellyfin.exe'
```

`-Profile Any` is the part that matters: it sidesteps the profile-ID condition entirely.
`-InterfaceAlias` keeps the port dark on the LAN and the internet, which is usually the point. Note its
one trap, shared with the OpenSSH rules on the same machine: the scope is by interface **alias**, so a
VPN client upgrade that recreates the adapter as `Tailscale 1` silently stops matching and the port goes
dark again exactly as if the rule were absent. `Get-NetFirewallRule -Name <n> | Get-NetFirewallInterfaceFilter`
is the one-line diagnosis.

Confirm afterwards from an actual peer, not from the host itself — a local `Invoke-WebRequest` to the
machine's own address succeeds regardless of inbound filtering and proves nothing.

## Elevation

`netsh wfp` needs an elevated token. Over OpenSSH as a member of Administrators this generally works
already; verify rather than assume:

```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
```
