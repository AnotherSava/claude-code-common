# Diagnosing a periodic input hitch on Windows

Symptom: typing is instant most of the time, then once every few seconds nothing appears for a
fraction of a second and the buffered keystrokes backfill at once. Measurements below are from one
real case (2026-09-02, Windows 11); the method is the reusable part.

## Split it first: one application, or the whole desktop

Type a line in Notepad. If it hitches there too, every hypothesis about the app you noticed it in is
dead, and you have eliminated a whole branch for the cost of ten seconds.

Do this **before** measuring anything, because a per-application suspect can survive arithmetic and
still be innocent. In this case the app was Claude Code, whose status line re-runs a command every
2 seconds; that command measured 110 ms typical and 275 ms peak, spawning `bash` → `bash` → `python`
plus a `conhost` each time. The cadence matched, the duration matched, and it was not the cause. A
coincidence that survives two checks is still a coincidence.

## The counters that tell you what it is *not*

Sample for ~30 s and read the **maxima**, not only the averages — a 200 ms stall is invisible in a
one-second average but shows in the peak.

| Counter | Reading in this case | What a bad value would mean |
|---|---|---|
| `\Processor(_Total)\% DPC Time` | 0.11% avg, 0.39% max | a driver |
| `\Processor(_Total)\% Interrupt Time` | 0.21% avg, 0.53% max | a driver or device |
| `\PhysicalDisk(_Total)\Avg. Disk sec/Transfer` | 0.001 s | storage |
| `\PhysicalDisk(_Total)\Current Disk Queue Length` | 0.07 avg | storage |
| `\Processor(_Total)\% Processor Time` | 9.8% avg | saturation |
| `\System\Processor Queue Length` | 0.1 avg | saturation |
| `\System\Context Switches/sec` | **82,000 avg, 162,000 peak** | scheduling churn |

Six of those seven were clean, which is what made the seventh worth believing. **Context switches per
second is the counter nobody quotes a threshold for**, and it was the only one out of range — an
idle desktop sits in the low thousands. Include it; it is the one that pointed at the answer.

## Ghost Explorer windows: the shell disagrees with the screen

`SeparateProcess = 1` under `HKCU:\...\Explorer\Advanced` ("launch folder windows in a separate
process") gives every folder window its own `explorer.exe`. Those processes can outlive anything
drawn on screen: the shell still counts the window as open, the process keeps doing the window's
work, and there is nothing visible to close.

Eight `explorer.exe` were running. Seven burned 11–15% of a core each — about 106% of one core,
continuously — and the user reported no File Explorer windows open at all. Both statements were true.

**Never take "I don't see any windows open" as an answer.** Ask the shell and the window manager
separately and compare; the disagreement is the finding:

```powershell
# what the shell believes is open
(New-Object -ComObject Shell.Application).Windows() | ForEach-Object { $_.LocationURL }

# what actually owns a visible top-level window, per PID:
# EnumWindows + IsWindowVisible + GetWindowThreadProcessId, grouped by process
```

Here the shell listed seven windows, all on `file:///C:/Users/<user>/AppData/Local/Temp`, while those
same seven processes owned **zero** visible windows between them (eight hidden top-level windows
each).

`%TEMP%` is why it cost so much. An open folder window watches its directory and re-enumerates on
every change notification, and `%TEMP%` is the busiest directory on a Windows machine — every
installer, browser download and script writes there. Seven watchers on it is self-sustaining load
that scales with how busy the box is rather than with anything the user is doing.

## Terminating them without killing the desktop

The shell — desktop, taskbar, Start — is also `explorer.exe`. Distinguish by **windows owned**, never
by PID order or start time: the shell owned 52 top-level windows with 10 visible; each ghost owned 8
with none visible. Parentage is a weak signal in both directions — the shell's parent had already
exited (so it shows as reparented) while the ghosts hang off `svchost.exe`, which is simply how
separate-process folder windows are spawned.

Guard the terminate on both facts, re-checked immediately before acting, since a PID can be recycled
between reading it and using it:

```powershell
$p = Get-CimInstance Win32_Process -Filter "ProcessId = $id"
if ($p.Name -ne 'explorer.exe') { continue }   # refuse
if ($visibleWindowCount[$id] -ne 0) { continue }  # refuse
Stop-Process -Id $id -Force
```

## Measure the same thing before and after, in one run

One script, one counter set, the same sample duration on both sides. Otherwise the outcome is "it
feels better", which is the claim you were asked to settle:

```
before   context switches/sec avg=76023  max=143962  | CPU 10.2%
after    context switches/sec avg=36267  max=66188   | CPU  6.9%
```

Also assert the thing you did **not** want to break — the shell was still alive with its 10 visible
windows afterwards, which is what makes "taskbar intact" a measurement rather than a hope.

One loose end worth stating rather than closing over: the newest ghost had been created hours before,
so whatever produces them is ongoing. Cleaning up is not the same as fixing the cause, and saying so
is part of the report.
