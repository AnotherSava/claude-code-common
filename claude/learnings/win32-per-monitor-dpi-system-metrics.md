# System metrics in a per-monitor DPI aware window

Use `GetSystemMetricsForDpi(index, GetDpiForWindow(hwnd))` for any metric that sizes a window's own geometry. Under `PER_MONITOR_AWARE_V2`, plain `GetSystemMetrics` answers at the **system DPI**: the primary monitor's scaling at login. It does not follow the window to another monitor. The two calls agree on a single monitor, and on several monitors at the same scaling, so a bug from mixing them up shows only on a machine whose monitors are scaled differently. CI and most dev boxes never see it.

## The custom-frame maximize inset

A window that removes its caption in `WM_NCCALCSIZE` still gets maximized the standard way. Windows positions it past the monitor edges by the frame thickness, `SM_CXFRAME + SM_CXPADDEDBORDER` (`SM_CYFRAME` vertically), measured at the window's DPI. While maximized, the handler has to inset the proposed client rect by that same amount.

Measured on agwinterm on 2026-10-09: the window was maximized on a 96 DPI monitor, and the system DPI was 144.

| Source | Frame | Padded border | Inset |
|---|---|---|---|
| `GetSystemMetrics` | 5 | 6 | 11 px |
| `GetSystemMetricsForDpi(…, 96)` | 4 | 4 | 8 px, which is the actual overhang |

Each side came out 3 px short. On the top side the gap shows as a light-grey strip (RGB 243,243,243), because DWM paints the caption in the non-client band. The other three sides were dark and could not be seen. Going the other way, a window scaled higher than the system DPI is not inset enough, so its content runs off the monitor. That direction is inferred and was not observed.

## Measuring it from outside

Read these values from a process set to `SetThreadDpiAwarenessContext(-4)` (PMv2). Without that, every coordinate is virtualized.

- `GetWindowRect` and `ClientToScreen(0,0)` plus `GetClientRect`
- `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS = 9)`
- `GetMonitorInfoW(MonitorFromWindow(hwnd))`, `GetDpiForWindow`, and `GetDpiForSystem`

For a maximized custom-frame window, the client rect has to equal the monitor rect, or the work area when there is a taskbar.

**Take the window handle from `Get-Process … | % MainWindowHandle`, not from `FindWindowExW(0, 0, $null, title)`.** PowerShell marshals `$null` for a `string` parameter as `""`, not as NULL. The call then matches only windows whose class name is empty, finds nothing, and returns no error.
