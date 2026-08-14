# Inspecting and changing multi-monitor layout on Windows

Recipes for reading the current display topology and rearranging it from a shell, plus the
traps that silently return plausible-but-wrong answers.

## Reading the layout

**Screen list (works, but logical coordinates).** The quickest reliable read:

```powershell
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
  '{0} Primary={1} Bounds={2},{3} {4}x{5}' -f $_.DeviceName, $_.Primary,
    $_.Bounds.X, $_.Bounds.Y, $_.Bounds.Width, $_.Bounds.Height
}
```

The numbers are **DPI-virtualized**, not physical pixels: a 3840x2160 panel at 150% scaling
reports 2560x1440. In a mixed-DPI setup the reported origins do not compose into a coherent
physical desktop either. Use this to learn *how many* displays are attached, which is primary,
and their relative arrangement — not to compute exact physical geometry.

**GPUs and the active mode.**

```powershell
Get-CimInstance Win32_VideoController |
  Format-List Name, PNPDeviceID, DriverVersion, CurrentHorizontalResolution,
              CurrentVerticalResolution, CurrentRefreshRate, Availability
```

`Availability` 3 = running/full power, 8 = off line. Virtual display adapters (Parsec,
DisplayLink, multi-seat software) appear here as real entries — check `Availability` before
blaming one for anything.

**Physical connection per monitor** — the one query that says *how* a panel is attached:

```powershell
Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorConnectionParams |
  ForEach-Object { '{0}  VideoOutputTech={1}' -f $_.InstanceName, $_.VideoOutputTechnology }
```

`VideoOutputTechnology` is `D3DKMDT_VIDEO_OUTPUT_TECHNOLOGY`:

| Value | Meaning | Value | Meaning |
|---|---|---|---|
| 0 | Other | 10 | DisplayPort (external) |
| 1 | HD15 (VGA) | 11 | DisplayPort (embedded) |
| 5 | DVI | 15 | Miracast |
| 6 | HDMI | 16 | Indirect wired |
| 7 | LVDS | 17 | Indirect virtual |

Drivers commonly report an HDMI-connected panel as **5 (DVI)**, since HDMI is electrically
DVI-compatible — so 5 means "DVI or HDMI", not "definitely DVI". Values 16/17 mark a display
that is not a real hardware output, which matters because such outputs often refuse
DXGI mode enumeration.

## The P/Invoke trap: a failed call that looks like a valid answer

`EnumDisplayDevices` / `EnumDisplaySettings` are the obvious way to read orientation and exact
physical mode, but they are easy to get subtly wrong from PowerShell, and the failure mode is
dangerous: the call returns 0 and leaves the struct **zero-filled**, which reads as
"orientation 0, position 0,0" — a perfectly plausible-looking result that is entirely fabricated.

Two specific causes seen:

- **`[ushort]` is not a PowerShell type accelerator.** `$dm.dmSize = [ushort][Marshal]::SizeOf(...)`
  throws `Unable to find type [ushort]`. Use **`[uint16]`**. When the assignment throws,
  `dmSize` stays 0 and `EnumDisplaySettings` rejects the struct.
- **`DEVMODEW` must be declared `CharSet = CharSet.Unicode`** and must contain *every* trailing
  field (`dmICMMethod` through `dmPanningHeight`). The W struct is 220 bytes; a declaration that
  stops after `dmDisplayFrequency` measures 188 and the call fails.

**Always check the return value before reading the struct.** If the call returned 0, the contents
are meaningless — do not report them.

When this fights back, prefer the WMI/Screen recipes above, or simply *re-assert* the state you
want rather than reading it: setting an orientation is idempotent, so it corrects the display
whether or not your read succeeded.

## MultiMonitorTool (NirSoft) from Git Bash

MultiMonitorTool is the practical way to script "disable these monitors" / "put them at these
coordinates". It identifies monitors by EDID-derived device ID:

```
MONITOR\<EDID-ID>\{4d36e96e-e325-11ce-bfc1-08002be10318}\####
```

`/SetMonitors` takes one quoted `Name=... Width=... Height=... DisplayFrequency=...
DisplayOrientation=... PositionX=... PositionY=...` argument per monitor. `DisplayOrientation`
follows the DEVMODE constants: **0 = normal, 1 = 90, 2 = 180, 3 = 270**. Adding `Primary=1`
marks the primary. Coordinates are physical pixels, with the primary's top-left at 0,0.

**The gotcha: invoking the exe directly from Git Bash hangs indefinitely.** Both
`./MultiMonitorTool.exe /scomma out.csv` and `./MultiMonitorTool.exe /SetMonitors "..."` block
forever, never write their output, and have to be killed. Route it through `cmd`, detached:

```bash
cmd //c "MultiMonitorTool.exe /SetMonitors \"Name=$MON DisplayOrientation=0 ...\"" >/dev/null 2>&1 &
sleep 8
taskkill //F //IM MultiMonitorTool.exe >/dev/null 2>&1
```

Always follow with the `taskkill` — a stray GUI instance otherwise lingers. Note that a `.cmd`
wrapper double-clicked or run by the user works fine; only the direct invocation from this shell
hangs, so "the user's script works" does not mean your invocation will.

**Disabling the primary is safe.** `/disable` on the primary monitor makes Windows promote a
surviving display automatically. But `/disable` alone never *sets* the survivor's mode — Windows
improvises it. If the single-display state must be deterministic, follow the disable with an
explicit `/SetMonitors` for the survivor, separated by a settle delay (`ping 127.0.0.1 -n 4 >nul`
is the idiom NirSoft-style `.cmd` scripts already use).

## Decoding an EDID manufacturer ID

Config files and logs often carry the manufacturer as a 16-bit integer (Overwatch's settings file
stores `DisplayManufacturerID = "27934"`). It is three 5-bit letters, `A`=1, packed big-endian —
so **byte-swap first**, then peel 5 bits at a time:

```
27934 = 0x6D1E  ->  swap -> 0x1E6D  ->  00111 10011 01101  ->  G S M   (LG Electronics)
        0x635A  ->  swap -> 0x5A63  ->  10110 10011 00011  ->  V S C   (ViewSonic)
```

The three letters are the prefix of the monitor's device ID (`GSM7706`, `VSCC336`), which is how
you tie a log line or an ini entry back to a specific physical panel.

## Claude Code sandbox: files must cross the process boundary

A file written by a *sandboxed* Bash command is not visible to external Windows processes. A
PowerShell script written to `/tmp` and then run via `powershell.exe -File <windows-path>` produces
no output and no error, and a tool told to write an export file appears to hang or silently
produce nothing. Run with the sandbox disabled whenever the artifact has to be read by a process
outside the Bash tool. Symptom to recognize: `ls` from Bash shows the file, but every Windows
process insists it does not exist.
