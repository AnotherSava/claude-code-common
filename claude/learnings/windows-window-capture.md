# Capturing a specific window on Windows (including occluded windows)

Verifying a desktop app's UI by screenshot has two pitfalls: full-screen capture grabs whatever the user has on screen (privacy + the target may be covered), and `Graphics.CopyFromScreen` of the window's rect still captures whatever is *visually on top* — a fullscreen video or overlay above the target wins, returning its pixels instead of the app's.

The fix is `PrintWindow` with `PW_RENDERFULLCONTENT`, which asks the window to render its own content into a DC regardless of occlusion or z-order. Flag `3` is the usual value and is `PW_CLIENTONLY | PW_RENDERFULLCONTENT` — the client-only half restricts the copy to the client area, which matters once you start comparing the result against a screen grab (see below). It works with WebView2-backed windows (Tauri, Electron, WebView2 apps), where the plain `PrintWindow` flag `0` often returns black.

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
[Win32Cap]::PrintWindow($h, $dc, 3)  # 3 = PW_CLIENTONLY | PW_RENDERFULLCONTENT
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
page or a dark one. The docs-relevance skill's `scripts/window-shot.ps1 -Method Alpha` implements
it, `-Popup` included for the menu case below.

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

## `PrintWindow`'s alpha channel is not the window's transparency

A capture taken with `PrintWindow` comes back **fully opaque** — alpha 255 in every
pixel, including the rounded corners of a window that is genuinely transparent on
screen. It is the window rendering itself into a DC, not the desktop compositor's
output, so there is no compositing and nothing for alpha to mean.

This reads as a definite answer and is not one. Asked whether a Tauri window with
`"transparent": true` was actually transparent on Windows, a `PrintWindow` grab
said alpha 255 at all four corners, which looks exactly like "no". The window was
transparent, and correctly rounded.

**Compare two captures of the same window instead**: `PrintWindow` (the window's own
surface) against a `CopyFromScreen` of its frame rect (what the compositor put on
the display). An opaque window composites to its own pixels, so the two agree; a
transparent one cannot, because the screen grab contains whatever is behind it.
Measured on a real widget:

| corner | PrintWindow (window's own surface) | Screen (composited) |
|---|---|---|
| top-left | `(243,243,243)` | `(241,241,241)` |
| bottom-left | `(0,0,0)` | `(210,210,210)` |

The two *disagreeing* is the proof: a corner where the screen grab differs from the
window's own surface is a corner showing what is behind it.

**Both captures have to cover the same rectangle, or the comparison invents its own
answer.** Flag `3` includes `PW_CLIENTONLY`, so the copy stops at the client area
while the screen grab above is of the window rect. On a decorated window those are
different rectangles, and `PrintWindow` writes nothing at all outside the client
area — so those pixels keep whatever the destination bitmap was initialised to, and
a corner reading "not the window's colour" there says nothing about transparency.

Two independent runs against decorated Explorer, both with a window-rect-sized
bitmap, both on an entirely opaque window:

| run | flag `2` | flag `3` |
|---|---|---|
| A | `(232,232,232)` at all four corners | `(232,232,232)` at TL, `(0,0,0)` at the other three |
| B | `(232,232,232)` except BR `(255,255,255)` | `(232,232,232)` at TL and TR, `(255,255,255)` at BL and BR |

The clipping is real and reproduces — flags `2` and `3` disagree in both runs. The
*value* does not: one run's unwritten region is black and the other's is white,
depending only on how the bitmap was allocated and cleared, and the affected corners
differ with the window's geometry. So do not grep for a sentinel colour; the tell is
that the two captures cover different rectangles, which makes everything outside the
client area inadmissible whatever it reads.

The widget measured above has custom chrome, where window rect and client rect
coincide and the clipping is a no-op — which is why the procedure held there.
Elsewhere, grab the client rect on both sides or pass flag `2`.

Then read the ramp inward along the corner diagonal on the composited grab, which
shows the antialiasing: `241, 240, 237, 213, 188, 23` down into the window's own
colour is a `border-radius` rendering correctly. A square corner steps straight from
background to content instead.

The two-exposure alpha solve under *Removing a background, and telling background
from chrome* answers the same question quantitatively, but it needs a backdrop
staged behind the window and a second exposure; the two-capture comparison needs
neither, so reach for it first when the question is just *is this transparent*.

## Two traps in the tooling itself

- **PowerShell 5.1 reads a `.ps1` as ANSI unless it has a BOM.** A UTF-8 em dash inside a
  double-quoted string becomes three bytes, one of which ends the string early — and the parser
  reports `Missing closing '}' in statement block` pointing at a line far below. Keep capture scripts
  pure ASCII, or save them UTF-8-with-BOM.
  - **It comes back through your tooling, not through your typing.** Editing one of these scripts with
    anything that writes UTF-8 *without* a BOM by default — Python's `write_text(encoding="utf-8")` is
    the usual culprit — silently strips it and reinstates the bug in a file that was previously fine.
    After a scripted edit, assert the first three bytes are `EF BB BF` on every `.ps1` that contains a
    non-ASCII byte; it is two lines and it is the only thing that catches this.
- **A simple `param()` block silently swallows arguments it does not declare.** Without
  `[CmdletBinding()]`, `script.ps1 -Method PrintWindow` puts the flag in `$args` and runs on with the
  declared parameters bound and no error at all — so a documented flag that was never implemented reads
  as working. With the attribute the same call fails with *"A parameter cannot be found that matches
  parameter name 'Method'"*. Put it on every script that takes parameters, especially one whose comment
  block tells an operator which flags to pass.
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

## Photographing a popup menu

A `TrackPopupMenu` menu (class `#32768`) survives only as long as nothing else takes focus, and every
step of the usual two-backdrop capture takes focus somewhere:

- **Don't raise it.** A popup never becomes the foreground window, so `SetForegroundWindow` fails,
  and the ALT keypress that normally earns the right to raise dismisses the menu outright.
- **Show the backdrops without activating them.** WinForms' `Form.Show()` activates; position and
  show the backdrop with `SetWindowPos(..., SWP_NOACTIVATE | SWP_SHOWWINDOW)` alone, inserted just
  below the menu in z-order. Activating anything ends the menu's modal loop, and the capture comes
  back as two empty backdrops.
- **Open it by message, not by click.** An app whose tray menu opens on a posted message can be
  driven without synthesized input. The Rust `tray-icon` crate opens it on `WM_USER_TRAYICON` (6002,
  in 0.24) with `lParam = WM_RBUTTONUP`, posted to its hidden `tray_icon_app` window, and shows it at
  the pointer, so place the pointer first. Those ids belong to the crate; re-check them after a bump.
- **Close it from outside.** `WM_CANCELMODE` posted to the menu's owner is the documented way to end
  another thread's menu; a posted `WM_KEYDOWN`/`WM_KEYUP` Escape to the menu window is the fallback.
  A real Escape keystroke may not reach it, because a menu opened by a posted message need not own
  the foreground.
- Windows 11 draws a light menu a **solid** light-grey frame with 6 px corners at 144 DPI, unlike a
  window's semi-transparent one (`windows-11-dwm-frame.md`).

## A window that opens under the pointer keeps its hover state

A window that appears under a resting pointer can show hover UI — a chart's tooltip — and moving the
pointer away afterwards with `SetCursorPos` does not clear it: the frame came back with the tooltip
in it. Park the pointer clear of where the window will open **before** opening it, and put it back
afterwards.

## An animated element has to be caught at a known phase

A shutter lands anywhere in a CSS animation, so a pulsing badge comes out at whatever opacity that
instant held — the first fixture-staged hero frame of the tauri dashboard caught both BLOCK pills at the
dim end of a 1.6s pulse between opacity 1 and 0.45. Measure the element in the capture and retake
until it reads near full, rather than hoping: find the pill's pixels by its colour, estimate its
opacity from how far they sit from the backdrop, and accept the frame at 0.9 or more (it took three
tries).

- **ClearType fringes match a coloured pill on two channels, not three.** Subpixel text antialiasing
  paints red and green fringes on ordinary text, and a pill-colour test on those channels alone counted
  them, so every frame read as dim. Requiring all three channels to agree and ignoring clusters under
  about 150 pixels left only the pills.
- **Two animated elements share a phase only if they started a whole number of periods apart.** A CSS
  animation starts when its element takes the class, so two rows that entered the pulsing state at
  arbitrary moments pulse out of step and no single shutter catches both bright. Staging them 120s apart
  (75 periods of 1.6s) put them in phase: the accepted frame read 0.91 and 0.98.

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

## A window hanging off a display comes back opaque black, at full size

A window-surface capture (`PrintWindow`, and anything built on it) reads what the compositor rendered, which is
why it can shoot a window that is occluded or behind another. What it cannot do is render the part that is off
the edge of a display: that returns **flat black at full alpha**, and the bitmap is still the full window size.
So the file looks complete, the dimensions are right, and a fifth of the picture is missing.

Measured: a 1520pt-wide window at x=3989 on a 1440-wide portrait monitor produced a 1522px frame whose last
239px were a black band where the right-hand gutter and two controls should have been. Nothing objected — not
the capture, not the PNG save, not a figure-manifest check that counts files rather than looking at them.

Two things follow for any capture script:

- **Place the window on a display that can hold it before sizing it.** A window remembers where it was last, so
  this cannot be left to luck — and the failure is invisible on the machine where it happens to be on the big
  monitor that day.
- **Assert on the result.** Sample a column just inside the far edge over the vertical middle; an opaque
  `0,0,0` run there is unrendered surface, because window furniture is essentially never pure black (a dark
  theme's own background is nearer `#1c1c1e`). It costs a few milliseconds and is the only thing standing
  between a silently truncated frame and a committed one.

macOS does not share the trap: `screencapture -l<id>` reads the window's backing store and returns the full
width whatever is on screen.
