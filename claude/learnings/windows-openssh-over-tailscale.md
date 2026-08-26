# Driving a Windows host over SSH on a tailnet

Reaching a Windows machine non-interactively from another machine. The coordinates for the actual hosts are
in `[[machines-private]]`; everything here is platform mechanics and applies to any Windows box.

## Tailscale SSH will not do it

Tailscale's SSH **server** component does not run on Windows — Linux and macOS only. A Windows node can
connect *out* via Tailscale SSH but can never accept it, and the failure is quiet: `tailscale status --json`
shows the peer online with no `sshHostKeys`, and `ssh` just times out. The supported paths are native Windows
OpenSSH over the tailnet, RDP, or an SSH server inside WSL2. Use native OpenSSH.

## Enabling it

Administrator PowerShell, once:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
```

`Add-WindowsCapability` **already creates its own firewall rule** (`OpenSSH-Server-In-TCP`, Private profile).
Adding a second `New-NetFirewallRule` for port 22 on top is redundant, and worse, it sets up the trap below.

## The admin-account key trap

For an account in the Administrators group, sshd reads `C:\ProgramData\ssh\administrators_authorized_keys`
and **ignores** the user's `~/.ssh/authorized_keys` entirely. It also ignores that file if its ACLs are not
restricted to Administrators and SYSTEM. Both failures present as `Permission denied (publickey)` — identical
to never having installed the key.

```powershell
$f = "$env:ProgramData\ssh\administrators_authorized_keys"
Add-Content -Path $f -Value $key -Encoding ascii
icacls $f /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

Pick the path by **group membership**, not by whether the shell is elevated —
`([Security.Principal.WindowsIdentity]::GetCurrent()).Groups -contains 'S-1-5-32-544'`. An
`IsInRole(Administrator)` check answers "is this shell elevated", which sends a non-elevated admin down the
profile branch and produces a key file sshd will never read.

## Scoping to the tailnet: check for more than one rule

Windows Firewall takes the **union** of Allow rules, so scoping one rule while another still allows the port
changes nothing — and looks like it worked. Enumerate everything on the port first:

```powershell
Get-NetFirewallRule -Direction Inbound -Enabled True | ForEach-Object {
  $r = $_; $p = $r | Get-NetFirewallPortFilter
  if ($p.LocalPort -contains 22) { $i = $r | Get-NetFirewallInterfaceFilter
    Write-Output ("{0} {1} {2} {3}" -f $r.Name, $r.Action, $r.Profile, ($i.InterfaceAlias -join "+")) } }
```

Then scope every one of them: `Set-NetFirewallRule -Name <rule> -InterfaceAlias Tailscale`.

Two things worth knowing before choosing this:

- **`-Profile` is usually the wrong lever.** The Tailscale adapter and the physical NIC are typically *both*
  `Private`, so a profile restriction does not separate them. Only the interface filter does.
- **Alias matching is brittle.** If a Tailscale upgrade recreates the adapter as `Tailscale 1`, the rules stop
  matching and SSH times out indistinguishably from "sshd was never installed".
  `Get-NetFirewallRule -Name sshd | Get-NetFirewallInterfaceFilter` is the check.

Tailnet-only is not the same as nobody: Tailscale does not gate services by default, so every device on the
tailnet reaches it. ACLs are the layer for that.

## Quoting: the default shell is cmd.exe

`ssh host "powershell -Command \"...\""` routes through **cmd.exe**, which eats `|`, `>`, `<` and `&` before
PowerShell ever sees them. A `>` inside the command silently redirects the output into a file named after the
next token — the command appears to do nothing while having worked perfectly.

Encode instead, and quoting stops mattering:

```bash
ENC=$(printf '%s' "$PS_SCRIPT" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')
ssh host "powershell -NoProfile -EncodedCommand $ENC"
```

Two more cleanups for readable output: start the script with `$ProgressPreference = "SilentlyContinue"` or
PowerShell emits a wall of `#< CLIXML` progress objects onto the stream, and pipe results through `tr -d '\r'`
locally since every line arrives CRLF.

## Probing reachability without fooling yourself

- **zsh has no `/dev/tcp`.** That is a bash feature; `(echo >/dev/tcp/host/port)` under zsh reports every port
  closed. Real false negatives came from this. Use `nc -z`.
- **Give it 8–10 seconds.** `nc -z -G 5 -w 5` returned "filtered" for a port that was genuinely open; the same
  probe at `-G 10 -w 10` connected. A short timeout is indistinguishable from a firewall drop.
- **Always probe a control port.** When testing that a rule closed port X, check a port you expect to stay
  open in the same run. Without it there is no way to tell "the rule worked" from "the probe is broken".
