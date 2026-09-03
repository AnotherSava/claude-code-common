# kitty terminal under WSL

Running the kitty terminal emulator from WSL on a Windows host, launched via a `kitty.vbs` script
kept with the user's other Windows tooling (outside any repo).

## Two kitty binaries coexist

- System kitty at `/usr/bin/kitty` — 0.32.2, whatever the distro packaged.
- Updated kitty at `~/.local/kitty.app/bin/kitty` — 0.45.0, installed from upstream.

The launcher and any `PATH` lookup will find the older one first unless pointed explicitly at the
`~/.local` path. When debugging rendering, always confirm *which* binary actually started.

## WSLg 1.0.71 broke Wayland rendering

Symptoms: ZINK/Mesa errors on startup, and a `50000x50000` stride error. This is the WSLg
compositor, not kitty's configuration — the same kitty build works elsewhere.

Two things to try, in order:

1. `LIBGL_ALWAYS_SOFTWARE=1` in the launcher's environment — forces llvmpipe and sidesteps the ZINK
   path entirely.
2. The updated kitty binary (0.45.0 above), which handles the compositor's geometry reporting
   differently from 0.32.2.

Neither is a fix for WSLg itself; they are workarounds for a specific WSLg version's Wayland surface
handling. If a later WSLg update changes the symptoms, re-test both rather than assuming the
workaround is still needed.
