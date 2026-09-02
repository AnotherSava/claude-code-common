# Diagnosing a latency complaint on Windows

Written after chasing "why is my ping 250?" for a game. The measurements below are from that session
(2026-09-01, Windows 11, wired 1 Gbps); the techniques are the reusable part.

## Windows does not expose a UDP socket's remote peer

`Get-NetTCPConnection` has a `RemoteAddress` column. **`Get-NetUDPEndpoint` has no remote columns at
all** — only `LocalAddress` and `LocalPort` — and no flag adds them. UDP is connectionless, so the
kernel's endpoint table holds no peer to report:

```
LocalAddress LocalPort
------------ ---------
0.0.0.0          65289
0.0.0.0          64444
0.0.0.0           4242
```

This matters more than it sounds, because the things people complain about the latency of — a game
server, a voice channel, a WireGuard tunnel — carry their real traffic over UDP. What the process
*does* show over TCP is login, auth and CDN endpoints, which are usually in a different datacentre
from the one whose RTT is being complained about. Measuring those and reporting the number is a
confident wrong answer.

Naming the UDP peer needs packet-level visibility: `pktmon` (built in since 1809) or a capture
driver, **both requiring elevation**. From a non-elevated shell the honest output is "I cannot
determine this, and here is why" — not an inference dressed as a finding.

## Time the TCP handshake when ICMP is filtered

Hosts routinely drop ICMP while answering on a port, so `Test-Connection` reporting nothing is not
evidence about reachability or distance. Time a connect instead — it works against any listening
port and measures the same round trip:

```powershell
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$c = New-Object System.Net.Sockets.TcpClient
$iar = $c.BeginConnect($ipAddr, $port, $null, $null)
if ($iar.AsyncWaitHandle.WaitOne(2000, $false) -and $c.Connected) {
    $sw.Stop(); $c.EndConnect($iar)
    $sw.Elapsed.TotalMilliseconds
}
$c.Close()
```

One host in that session gave **no ICMP reply whatsoever** and measured min 53.8 / avg 58.7 / max
75.6 ms over five connects to its game port. Reporting it as unreachable would have been wrong; so
would reporting the auth server's 36 ms as "the ping".

## Localise the step before blaming anything

Ping outward in widening rings, then trace. The shape of the answer is where the number jumps:

| Probe | Result |
|---|---|
| default gateway | 0.2 ms |
| nearby anycast resolver (`1.1.1.1`) | 1.2 ms |
| `8.8.8.8` | 4.9 ms |
| the destination's edge | 34.5 ms |

```
 7     5 ms  <last hop inside the ISP>
 8    55 ms  <first hop inside the destination's own AS>   <- +50 ms in one hop
10    54 ms
11    54 ms
```

Hops 1–7 at ~5 ms and a 50 ms step at hop 8 says everything up to the destination's border is
healthy and the distance is being added *inside their network*, where nothing at this end changes
it. That separation is the deliverable. It is also what stops a clean local network being measured a
third time — [[feedback_dont_recheck_known_answers]].

## Rule out the cheap confounders in one pass, with numbers

Each of these is one command, and each is worth stating as a measured value rather than an
impression, because "the network looks fine" is exactly the claim the user is disputing:

- **Utilisation against link speed.** Sample `Get-NetAdapterStatistics` twice N seconds apart and
  divide. 40 KB/s down on a 1 Gbps link is not congestion, and saying so with the figure ends the
  argument.
- **Bufferbloat.** Ping the *same* target before and during that load. Unchanged latency under load
  (1.2 ms → 1.5 ms) rules out queue buildup; a large rise localises it to the uplink queue.
- **Adapter errors.** `ReceivedPacketErrors` / `OutboundDiscardedPackets` at 0 rules out a bad cable
  or a struggling NIC.
- **A tunnel that is installed but not carrying traffic.** A VPN adapter existing proves nothing —
  check whether it holds the default route. For Tailscale, `tailscale status --json` → `ExitNodeStatus`
  is `null` when no exit node is set, so the tunnel is not in the path regardless of the adapter's
  presence or its impressive reported link speed.
- **Wired or wireless.** `Get-NetAdapter | Where-Object Status -eq 'Up'`, plus
  `netsh wlan show interfaces` — which prints nothing at all on a wired-only machine, itself the
  answer.

## Two mechanical traps in the probing itself

- **Write the probe to a `.ps1` and run it with `-File`.** Git Bash mangles backslashes inside
  `powershell -Command "..."`, and the script must be **pure ASCII** — PowerShell 5.1 reads a
  BOM-less file as the ANSI codepage, so one em dash inside a string produces a parse error pointing
  at an unrelated line far below. Both traps are in `bash-portability.md` and
  `windows-window-capture.md`; they bite here because a diagnostic script is exactly the kind of
  throwaway nobody saves with a BOM.
- **A truncating pager hides the part you wanted.** Piping a long probe through `head -N` silently
  drops the latency block at the end. Put the conclusion-bearing section first, or raise the limit.
