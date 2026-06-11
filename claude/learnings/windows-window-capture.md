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
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
Add-Type -AssemblyName System.Drawing
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

- On a per-monitor-DPI (scaled) monitor, `GetWindowRect` can under-report relative to the window's DPI-scaled rendered content, so a bitmap sized exactly to the rect **clips the bottom/right edge** — losing whole rows of a content-fit / auto-resize window. Re-reading the rect does **not** help (the rect is genuinely smaller than the painted content). Fix: size the bitmap **larger** than the rect (e.g. `1.6×w, 1.8×h`), clear it to a sentinel color (magenta) before `PrintWindow` so the real content boundary is visible, then crop. The sentinel margin also confirms you captured everything rather than clipping.
- If the window resizes between `GetWindowRect` and `PrintWindow` (e.g. a content-fit auto-resize), the bitmap clips or letterboxes — capture again with a fresh rect (and oversize the bitmap per the previous point).
- Prefer this over full-screen `CopyFromScreen` even when the window is visible: it avoids capturing the user's unrelated screen content.
