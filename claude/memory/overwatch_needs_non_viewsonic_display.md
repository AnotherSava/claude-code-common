---
name: overwatch_needs_non_viewsonic_display
description: Overwatch cannot launch when the ViewSonic VX3211-4K is the only enabled display; DXGI reports zero display modes for that panel
metadata:
  type: project
---

On the Windows desktop with three monitors (Acer `ACI27B2` portrait, LG `GSM7706` 4K primary,
ViewSonic `VSCC336` / VX3211-4K 4K), Overwatch fails with "No compatible graphics hardware was
found. (0xE0070100)" whenever the ViewSonic is the **only** enabled display. Confirmed on
2026-08-11 by reading the game's own log: `IDXGIOutput::GetDisplayModeList` returns
`0x887A0022 DXGI_ERROR_NOT_CURRENTLY_AVAILABLE` for that panel, so the output reports
`mode count: 0`, the RTX 3050 is discarded as having no usable outputs, and adapter enumeration
comes back empty.

**Why:** it is a property of that panel's output, not of the GPU, the driver, or the game's saved
settings. Ruled out by direct test: removing the `[GPU.N]` display pin from `Settings_v0.ini`,
setting rotation from 180 back to 0, and explicitly forcing native 3840x2160 @ 60 all produced the
identical failure. In multi-monitor mode the game silently uses the LG instead, which is why the
problem only appears in single-display mode. Unproven correlation worth testing if it resurfaces:
the LG is the only panel *not* on DisplayPort (it reports DVI/HDMI; both DP-connected panels are
the rotated ones, and the Acer alone was never tested).

**How to apply:** before concluding the GPU or drivers are at fault, read
`%USERPROFILE%\Documents\Overwatch\Logs\Overwatch.log` — it is rewritten on every launch and names
the real reason. If a single-display mode must coexist with Overwatch, keep the LG enabled rather
than the ViewSonic. Full diagnosis technique and the headless launch harness are in the
`overwatch-display-enumeration` learning; monitor-layout tooling is in
`windows-display-configuration`.
