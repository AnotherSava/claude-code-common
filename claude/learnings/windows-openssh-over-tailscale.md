# Driving a Windows host over SSH on a tailnet

Reaching a Windows machine non-interactively from another machine. The coordinates for the actual hosts are
in `[[machines-private]]`; everything here is platform mechanics and applies to any Windows box.

## Tailscale SSH will not do it

Tailscale's SSH **server** component does not run on Windows — Linux and macOS only. A Windows node can
connect *out* via Tailscale SSH but can never accept it, and the failure is quiet: `tailscale status --json`
shows the peer online with no `sshHostKeys`, and `ssh` just times out. The supported paths are native Windows
OpenSSH over the tailnet, RDP, or an SSH server inside WSL2. Use native OpenSSH.

**On macOS that support is variant-dependent, so "Linux and macOS" oversells it.** The SSH server needs the
open-source `tailscale` + `tailscaled` CLI build; the App Store and standalone (macsys) GUI variants cannot
host it, and one of those is what a Mac normally runs. A tailnet SSH policy rule is required on top. So the
same quiet `sshHostKeys: null` means "not enabled" *or* "cannot be enabled here", and the two are
indistinguishable from the far end — `tailscale ssh <host>` just falls through to a plain port-22 dial and
reports `connection refused`. Establish which variant a Mac runs before proposing Tailscale SSH for it;
otherwise native Remote Login is the shorter path.

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

## ssh.exe as a *client*, spawned inside an sshd session, cannot forward stdin

Driving a Windows box over SSH and having *it* ssh somewhere else — a peer scan, a relayed
command — puts ssh.exe inside an sshd session. There it hangs the moment it has to forward any
stdin at all, and the hang is silent: it prints its version banner and stops, before the line where
it would normally say it is reading its config.

Measured 2026-09-14, same session, same target, only the handle type differing:

| call | handles | result |
|---|---|---|
| `ssh host "echo hi"` (no stdin data) | pipes | **hangs** |
| `ssh host "echo hi"` (no stdin data) | files | 0.2 s |
| `ssh host "cat"` with 53 KB in | files | 0.2 s |
| `ssh host "python3 -"` with 18 bytes in | pipes | **hangs** |

Payload size is irrelevant — 18 bytes hangs exactly like 53 KB. `git` and `gh` on the same box,
in the same session, use pipes happily, so this is ssh.exe specifically rather than subprocess
pipes in general.

**From an ordinary console on that machine it all works.** Confirmed by having something with a real
console run the same probe (`SSH_CONNECTION` empty, `SESSIONNAME=Console`): all four calls returned,
including piping a 53 KB script into the far side's interpreter. So the defect belongs to the
*nesting*, not to ssh.exe.

Two consequences, and the second is the expensive one:

- **Use real file handles, not `capture_output=True` / `input=`,** for any ssh.exe you spawn from
  Python on Windows. `tempfile.TemporaryFile()` for all three handles costs a few lines and works in
  both contexts.
- **A test harness that reaches the box over SSH cannot test that box's own outbound ssh.** Every
  route onto the machine is an sshd session, so the harness is inside the fault it is measuring, and
  the symptom — a 300 s timeout reported as the far end being unreachable — looks exactly like a real
  network or auth failure. Nothing on the machine can tell you otherwise. Get a process with a real
  console there to run the probe: the user's own shell, or the Claude session already running on that
  box via [[peer_messaging]]'s dashboard relay. Then have it write to a file you read back over SSH,
  per [[feedback_route_output_not_paste]].

## You cannot drop privileges here, and `runas` says nothing about it

An sshd session for an account in the Administrators group arrives **elevated** — High mandatory
level, `SeCreateSymbolicLinkPrivilege` enabled — so anything measured from it is measured with
rights an ordinary desktop shell does not have. Testing what happens *without* elevation needs a
different route, and the obvious one is not it:

```
runas /trustlevel:0x20000 "cmd /c C:\path\to\probe.cmd"
```

Measured 2026-09-18: that returns **exit 0** and runs nothing. No output file appeared anywhere
under the profile, and `runas` printed no error — it needs an interactive desktop to start the new
console on, and an sshd session has none. A scheduled task registered at `RunLevel Limited` would
get a filtered token, but it runs in the logged-on user's session and flashes a console on their
screen, which [[feedback_no_flashing_windows]] rules out.

What is left is a person at that machine running the command in an ordinary PowerShell window, with
the result written to a file this side reads back over SSH per [[feedback_route_output_not_paste]].
Say that plainly rather than reporting the elevated measurement as though it covered both.

## Probing reachability without fooling yourself

- **zsh has no `/dev/tcp`.** That is a bash feature; `(echo >/dev/tcp/host/port)` under zsh reports every port
  closed. Real false negatives came from this. Use `nc -z`.
- **Give it 8–10 seconds.** `nc -z -G 5 -w 5` returned "filtered" for a port that was genuinely open; the same
  probe at `-G 10 -w 10` connected. A short timeout is indistinguishable from a firewall drop.
- **Always probe a control port.** When testing that a rule closed port X, check a port you expect to stay
  open in the same run. Without it there is no way to tell "the rule worked" from "the probe is broken".
