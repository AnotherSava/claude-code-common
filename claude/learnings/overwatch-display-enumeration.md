# Overwatch "No compatible graphics hardware was found" (0xE0070100)

The dialog blames the GPU, and every search result tells you to reinstall drivers. It is often
not the GPU at all: Overwatch discards an adapter whose **outputs report zero display modes**, so
a perfectly healthy card gets thrown away because of the *monitor* it is attached to.

Related: [windows-display-configuration.md](windows-display-configuration.md) for reading and
changing the monitor layout you will be testing against.

## Read the game's own log first

`%USERPROFILE%\Documents\Overwatch\Logs\Overwatch.log`

Rewritten on **every** launch attempt, including failed ones, and it records the whole DXGI
enumeration: one block per GPU, one per display, then the verdict. The failing shape:

```
pm_dxgi::Instance::QueryGpu: SDR mode count: GetDisplayModeList failed. Error Code: 0x887a0022
prism: Info: Display 0
prism: Info:   name: VX3211-4K
prism: Info:   refreshRate: 0/0
prism: Info:   nativeRefreshRate: 59997/1000
prism: Info:   supports4k: 0
prism: Info:   mode count: 0
Discarding unusable adapter [no modes] NVIDIA GeForce RTX 3050
No usable outputs for adapter NVIDIA GeForce RTX 3050.
Enumerated 0 adapters.
Adapter enumeration failed
```

`0x887A0022` is `DXGI_ERROR_NOT_CURRENTLY_AVAILABLE` from `IDXGIOutput::GetDisplayModeList`.
Note that the EDID-derived fields (`name`, `nativeSize`, `nativeRefreshRate`) are read correctly —
Windows knows the panel perfectly well. Only the *mode list* is empty, and `supports4k: 0` /
`refreshRate: 0/0` are downstream consequences of that empty list, not independent facts.

Microsoft documents this error for `GetDisplayModeList` when called from a Remote Desktop Services
session or a Session 0 process. Field reports add: video dongles and USB display adapters in the
signal chain, and a desktop running at a refresh rate the panel does not natively advertise.

## Headless test harness — iterate without a human clicking Play

Neither launcher route starts the game from a shell:

- `Battle.net.exe --exec="launch Pro"` returns immediately, game never starts
- `Overwatch Launcher.exe` exits without starting the game

Running the real binary directly **does** work, reproduces the failure, and writes the log:

```bash
cd "<overwatch-install>/_retail_" && ./Overwatch.exe >/dev/null 2>&1 &
sleep 25
taskkill //F //IM Overwatch.exe >/dev/null 2>&1
grep -E "mode count|Discarding|Enumerated [0-9]|Adapter enumeration" "$USERPROFILE/Documents/Overwatch/Logs/Overwatch.log"
```

Read the verdict from the log rather than looking at the screen. Resident-memory is a good
liveness signal: a failed launch sits flat at **~165 MB**, while a real load climbs into the GB
range within seconds. This turns a "launch it and tell me what you see" loop into an automated
one — worth setting up before testing hypotheses, since each test otherwise costs a round trip.

## The display pin in Settings_v0.ini — a tempting dead end

`%USERPROFILE%\Documents\Overwatch\Settings\Settings_v0.ini` has a `[GPU.N]` block naming the
display the game last used:

```ini
[GPU.6]
DisplayName = "LG HDR 4K"
DisplayManufacturerID = "27934"     ; EDID "GSM" = LG
DisplayProductID = "30470"
GPUName = "NVIDIA GeForce RTX 3050"
```

Blizzard's blanket advice is to delete the whole file, which resets every graphics setting.
Deleting only the `[GPU.N]` block resets the display pin while preserving `[Render.*]`,
`[Sound.*]` and `[Input.*]`; the game regenerates it on the next successful launch. Use `awk` to
drop the section and re-assert CRLF afterwards (`awk` on Git Bash normalizes line endings):

```bash
awk '/^\[GPU\./ { skip=1; next } skip && /^\[/ { skip=0 } skip { next } { print }' in.ini > out.ini
sed -i 's/\r*$/\r/' out.ini
```

**But a stale pin is not the cause of 0xE0070100.** Verified: removing the block changed nothing
when the underlying problem was mode enumeration. Check the log before editing the ini — if it
says `mode count: 0`, the pin is irrelevant.

## What does not fix a `mode count: 0` display

All tested against the same panel that failed as the sole display, each ruled out by relaunching
and re-reading the log:

| Suspect | Test | Outcome |
|---|---|---|
| Stale display pin | removed `[GPU.N]` | no change |
| Screen rotation | set orientation 180 -> 0 | identical failure |
| Odd resolution/refresh | explicitly set native 3840x2160 @ 60, 32-bit | identical failure |
| GPU or driver | same card drives the game fine in multi-monitor mode | not the GPU |

The practical conclusion: when one panel enumerates no modes, the fix is to keep a *different*
display enabled (in a multi-monitor setup the game silently picks a working output, which is why
the bug only appears when the bad panel is alone), or to change how that panel is physically
attached. Suspect the connection path — adapters, dongles, MST hubs, and indirect-display drivers
are the documented causes of an output that Windows can describe but DXGI cannot enumerate.
