# Simulating mouse gestures against a Windows app from a script

Some behaviors only exist inside the OS's *modal move/resize loop* — Aero Snap, drag-to-top maximize, snap-to-side, double-click-to-maximize on a custom title bar. They can't be reached by posting messages (`PostMessage`/`SendMessage` skips the loop) and can't be verified by inspection. Driving the real mouse is the only way to test them, and it works well enough to use as a regression check.

Companion to `windows-window-capture.md` (which covers screenshotting the result) — the DPI rule below is the same one.

## Recipe

```powershell
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class G {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr c);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
}
"@
[void][G]::SetProcessDpiAwarenessContext([IntPtr](-4))   # PerMonitorV2 — before any coordinate call
# grab point → press → walk → dwell → release
[void][G]::SetCursorPos($grabX, $grabY); Start-Sleep -m 250
[G]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -m 250      # LEFTDOWN
for ($s = 1; $s -le 20; $s++) { [void][G]::SetCursorPos($x[$s], $y[$s]); Start-Sleep -m 30 }
Start-Sleep -m 700                                                         # dwell so snap logic fires
[G]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)                          # LEFTUP
```

- **Walk, don't jump.** A single `SetCursorPos` to the target does not trigger snap; ~20 steps at 30 ms plus a ~700 ms dwell at the edge does.
- **Double-click** is two down/up pairs at the same point, ~100 ms apart — well inside `GetDoubleClickTime`, and the position must not move or the app sees two single clicks.
- **DPI-awareness of the *driver* process is mandatory** (`SetProcessDpiAwarenessContext(-4)`, not `SetProcessDPIAware()`), or `SetCursorPos` and `GetWindowRect` are virtualized on a scaled monitor and every coordinate lands wrong.
- `*W` imports need `CharSet.Unicode` or strings come back as their first character (`GetWindowTextW` returning `"C"` for `"Claude Code Dashboard"`).

## Prefer `mouse_event` over `SendInput` here

`SendInput` is the modern API, but hand-rolling its `INPUT` struct in PowerShell is a trap. On x64 the real layout is 4-byte `type` + 4 bytes of padding + a 32-byte `MOUSEINPUT` union = **40 bytes**; add any field of your own (a trailing `long` "pad", say) and `Marshal.SizeOf` returns 48, `SendInput` rejects the mismatched `cbSize`, and it fails **silently** — the cursor stays put while you misread whatever it was already near as the result. `mouse_event` is formally deprecated, needs no struct, and drives the same input queue.

If you do use `SendInput`, its absolute coordinates are normalized 0–65535 across the *virtual desktop* (`MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE`), whose origin (`SM_XVIRTUALSCREEN`) is negative when a monitor sits left of the primary. `SetCursorPos` takes plain screen coordinates and sidesteps the arithmetic entirely.

## It is flaky — always assert the positive

A drag sometimes doesn't take at all: the window never moves, apparently because activation swallowed the press. **A "nothing happened" result is therefore ambiguous** — it means either the behavior is blocked (what you wanted to prove) or the gesture never started. Guard against reading a dud run as a pass:

- Assert the window's rect actually changed before concluding a *drag* did nothing untoward, and re-run once before believing any negative result.
- Better, pair every test with a **positive control** that must produce the effect.

## Live-style control experiment

The strongest control needs no rebuild: toggle the relevant window style on the *running* app's HWND and repeat the identical gesture.

```powershell
$style = [int64][G]::GetWindowLongPtrW($h, -16)                    # GWL_STYLE
[void][G]::SetWindowLongPtrW($h, -16, [IntPtr]($style -bor 0x00010000))   # WS_MAXIMIZEBOX
[void][G]::SetWindowPos($h, [IntPtr]::Zero, 0,0,0,0, 0x0027)       # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED
# …run the gesture; then restore $style the same way
```

That turns "the drag didn't maximize it" into "the drag maximizes it with the bit, and doesn't without" — causality instead of correlation, in one session against one binary. Note it only works for behavior the *OS* gates on a style; a toolkit that keeps its own copy of the flag (tao's `WindowFlags`, for one) won't notice the external edit, so paths that run through the toolkit can't be controlled this way.

Useful constants: `GWL_STYLE` -16, `WS_MAXIMIZEBOX` 0x00010000, `WS_MINIMIZEBOX` 0x00020000, `WS_SIZEBOX`/`WS_THICKFRAME` 0x00040000, `SWP_FRAMECHANGED` 0x0020, `MOUSEEVENTF_LEFTDOWN` 0x0002, `MOUSEEVENTF_LEFTUP` 0x0004.

## Leave no trace

You are driving the user's actual mouse against their actual window. Capture the window rect and cursor position before the test and restore both after — including `ShowWindow(hwnd, SW_RESTORE)` when the run maximized the window, and the original style if you toggled one. Keep the whole gesture under a second or two.
