# Capturing a specific window on Windows (including occluded windows)

Verifying a desktop app's UI by screenshot has two pitfalls: full-screen capture grabs whatever the user has on screen (privacy + the target may be covered), and `Graphics.CopyFromScreen` of the window's rect still captures whatever is *visually on top* — a fullscreen video or overlay above the target wins, returning its pixels instead of the app's.

The fix is `PrintWindow` with `PW_RENDERFULLCONTENT` (flag `3`), which asks the window to render its own content into a DC regardless of occlusion or z-order. It works with WebView2-backed windows (Tauri, Electron, WebView2 apps), where the plain `PrintWindow` flag `0` often returns black.

Getting the window handle: `(Get-Process <name>).MainWindowHandle` is reliable. `FindWindowW($null, "<title>")` can fail to find Tauri/WebView2 windows even when the title matches — don't debug that path, just use the process handle.

PowerShell snippet (note: `Add-Type` and its usage must be in the **same tool call/session** — shell state does not persist between PowerShell tool invocations):

```powershell
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Cap {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
Add-Type -AssemblyName System.Drawing
[Win32Cap]::SetProcessDPIAware() | Out-Null  # MUST run before GetWindowRect on scaled monitors
$h = (Get-Process my-app).MainWindowHandle
$r = New-Object Win32Cap+RECT
[Win32Cap]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L; $ht = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap($w, $ht)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[Win32Cap]::PrintWindow($h, $dc, 3)  # 3 = PW_RENDERFULLCONTENT
$g.ReleaseHdc($dc)
$bmp.Save("$env:TEMP\capture.png"); $g.Dispose(); $bmp.Dispose()
```

Caveats:

- **Make the capturing process DPI-aware first** (`SetProcessDPIAware()` before `GetWindowRect`). A DPI-unaware PowerShell process receives *virtualized* (scaled-down) coordinates on a scaled monitor — a window truly 652×111 physical px on a 1.5× monitor reads as 435×74 (÷1.5), and a bitmap sized to that rect drops the bottom/right third of the rendered content. This silently reads as "content is clipped / not rendering" and is very easy to misdiagnose (chasing a phantom layout/clip bug). Cross-check the rect against the app's own logged window size if available, and note that the rect's position also reveals which monitor it's on (a large x like 3186 = secondary monitor, often the scaled one). Once the process is DPI-aware, `GetWindowRect` returns true physical px and a rect-sized bitmap captures everything — no oversize/sentinel needed.
- *(fallback, if you can't set DPI awareness)* Size the bitmap **larger** than the rect (e.g. `1.6×w, 1.8×h`), clear it to a sentinel color (magenta) before `PrintWindow` so the real content boundary is visible, then crop. The sentinel margin also confirms you captured everything rather than clipping.
- If the window resizes between `GetWindowRect` and `PrintWindow` (e.g. a content-fit auto-resize), the bitmap clips or letterboxes — capture again with a fresh rect (and oversize the bitmap per the previous point).
- Prefer this over full-screen `CopyFromScreen` even when the window is visible: it avoids capturing the user's unrelated screen content.
- **Driving the app to a state before capture** *(see also the UI Automation section below)*: to position the cursor or trigger the app at exact physical coordinates against a PerMonitorV2 app, declare the *driver* (PowerShell) process PerMonitorV2-aware — `SetProcessDpiAwarenessContext((IntPtr)(-4))`, not just `SetProcessDPIAware()` — otherwise `SetCursorPos` and `Screen` bounds are DPI-virtualized and land wrong on a scaled monitor. `keybd_event` fires `RegisterHotKey` global hotkeys and is seen by `GetAsyncKeyState`, so you can trigger the app's hotkey and hold modifiers (e.g. Shift) programmatically. Park the cursor away from the region of interest before capturing so the crosshair/pointer isn't baked into the shot. For gestures the OS only honors inside a real move/resize loop — dragging, snapping, double-clicking a custom title bar — see `windows-gesture-simulation.md`.

## The edges are where a screen capture goes wrong

`PrintWindow` sidesteps all of this by rendering the window's own content. When you must use
`CopyFromScreen` instead — a menu, a popup, anything `PrintWindow` returns blank for — the rectangle
you choose decides what junk comes with it. Three separate defects, found in this order, each one
looking like the previous fix had worked:

- **`GetWindowRect` includes the invisible DWM resize border** (~7-8 px a side on Win10+), so a capture
  of that rect has desktop down both edges. `DwmGetWindowAttribute(h, 9 /* DWMWA_EXTENDED_FRAME_BOUNDS */, ...)`
  returns the frame actually drawn.
- **The visible frame still carries Windows 11's own ~2 px border**, and that border follows the *OS*
  light/dark setting — so it is near-black around a window rendering in the light theme. It reads as
  "a dark frame appeared around my screenshot".
- **The client area (`GetClientRect` + `ClientToScreen`) has neither**, and drops the title bar too.
  But its **bottom** corners sit on the window's rounded frame, so a few pixels there are the window's
  own dark border curving inward. The top corners are square, because they sit below the title bar.

## Removing a background, and telling background from chrome

Rounded corners are antialiased and a translucent window is translucent everywhere, so boundary pixels
are a *blend* of subject and whatever was behind. No crop separates them: trim less and a fringe
survives, trim more and content goes. Capture twice over known backdrops and solve per pixel — for
colour `C` at coverage `a` over backdrop `B` the screen shows `O = C*a + B*(1-a)`, so over black
`O_k = C*a`, over white `O_w = C*a + 255*(1-a)`, giving `a = 1 - (O_w - O_k)/255` and `C = O_k / a`.
Exact for any partial coverage; write it as a PNG with alpha and it composites correctly on a light
page or a dark one.

**A known shape needs only one capture.** The solve above exists because both the colour and the
coverage are unknown at a boundary pixel. When the subject is a shape you can *describe* — a rounded
rectangle, a panel, a card — its geometry supplies the coverage, and one capture is enough: build the
mask analytically at 8x and downsample. Two details decide whether it looks right.

- **Inset one pixel.** A mask alone still fringes, because the pixels it half-covers really are half
  backdrop. Dropping that ring takes the fringe with it, at the cost of a corner one pixel tighter,
  which is invisible at viewing size.
- **Do not un-blend an inset edge.** With the inset the boundary sits *inside* the subject, so a
  partial pixel is pure subject being antialiased by the mask; subtracting a backdrop that is not in
  it over-brightens toward white. Seen as a 7%-alpha white fringe along one edge that passed every
  numeric check and was only visible on screen. Un-blend only at zero inset.

Masking by shape also sidesteps a backdrop too close to the subject to colour-key — in one case a
panel fill and a page background 28 levels of blue apart, which no threshold separates. Two
consequences: any border added afterwards must trace the **shape**, because a keyed image has no
rectangular edge for a canvas-wide box to sit on; and estimate the subject's own luminance from a
**median over a grid**, since one sample lands on text as readily as on fill and will choose a dark
outline for a dark panel.

Show the backdrop as a borderless form slotted directly *beneath* the target with
`SetWindowPos(backdrop, target, ..., SWP_NOACTIVATE)` — not topmost, so the target keeps its z-order
and activation. Pad it past the corners.

**The recovered colour is also the diagnosis.** A fringe that comes back as the subject's own colour
at rising alpha is background, and the alpha removes it. One that comes back *dark at ~50% coverage*
is **chrome** — a border or shadow belonging to the window — and no background removal will touch it,
because preserving it faithfully is the method working correctly. The only fix for chrome is to not
include it: inset until all four corners are fully opaque, measured per capture so it tracks the OS
corner radius and the display scale instead of hardcoding one machine's.

**Do not verify with a threshold tuned to the previous defect.** Checking "is any perimeter pixel
dark?" as `R+G+B < 200` catches near-black desktop bleed and sails past a `6D->93->B8->DE` antialiased
ramp that is glaring against a `#F3F3F3` window. Assert on what the pixel *becomes* over the
background it will be shown on (`C*a + 255*(1-a)` for a white page) and compare that against the
window's own fill.

## Two traps in the tooling itself

- **PowerShell 5.1 reads a `.ps1` as ANSI unless it has a BOM.** A UTF-8 em dash inside a
  double-quoted string becomes three bytes, one of which ends the string early — and the parser
  reports `Missing closing '}' in statement block` pointing at a line far below. Keep capture scripts
  pure ASCII, or save them UTF-8-with-BOM.
- **Per-pixel work belongs in C# via `Add-Type`, not a PowerShell loop.** A 1300x1650 window is 2.2M
  pixels; `GetPixel`/`SetPixel` in script takes the better part of a minute, while `LockBits` +
  `Marshal.Copy` + a C# loop is instant.

## Driving a tray icon and its menu with UI Automation

- The tray icon is a `Button` whose `Name` is the app's tooltip; find it by walking
  `RootElement.FindAll(Descendants, ControlType.Button)`. If its rect looks off-screen, the *driver*
  process is DPI-virtualized — see the DPI caveat above.
- **A synthetic right-click opens the tray menu only sometimes.** Poll for the menu item for a few
  seconds rather than sleeping a fixed interval, and re-run on failure; a script that assumes it
  opened fails intermittently and looks like a different bug each time.
- **`InvokePattern.Invoke()` on a menu item that opens a modal dialog blocks and eventually throws a
  COM timeout** — the dialog's message loop never returns to the caller. The dialog *does* open. Click
  the item at its `BoundingRectangle` centre instead.
- **`AutomationElement.FromHandle(hwnd)` is reliable where a global `Descendants` search is not** — the
  latter can hand back a stale element whose children come up empty, which reads as "the window has no
  controls".

## A desktop-wide UI Automation search dies on one bad provider

The obvious helper walks every descendant of the desktop root:

```powershell
$ua::RootElement.FindAll([TreeScope]::Descendants, $condition)   # fragile
```

On a machine running any application whose automation provider misbehaves, this throws
`RPC_E_SERVERFAULT` (`0x80010105`) outright — and it is not transient, so retrying never clears it.
Every capture script on that machine fails at once, for a window none of them care about. The error
names no culprit, so it reads like a bug in the script that happened to run first.

Walk top-level windows instead and skip the ones that fault:

```powershell
foreach ($top in $ua::RootElement.FindAll($scope::Children, [Condition]::TrueCondition)) {
  try {
    foreach ($el in $top.FindAll($scope::Descendants, $condition)) {
      if ($el.Current.Name -like $Name) { return $el }
    }
  } catch { continue }
}
```

Same coverage, one bad application skipped instead of taking the run down. Worth fixing in the shared
helper rather than working around per script: every capture script inherits the fault.

Two related notes for driving a menu this way:

- A WinForms `ContextMenuStrip` lives in a window whose class name is a generated
  `WindowsForms10.Window.*`, **not** `#32768` — filtering by class to find the menu finds nothing.
  Enumerate all top-level windows and look for the `MenuItem` by name.
- A synthetic right-click on a tray icon opens the menu only *sometimes*. Poll-after-one-click never
  succeeds when the click did nothing; **re-click** in a loop (up to ~6 attempts, ~900 ms apart) and
  poll after each.
