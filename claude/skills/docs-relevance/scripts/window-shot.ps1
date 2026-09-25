<#
.SYNOPSIS
  Capture one top-level window to a PNG at true device resolution.

.DESCRIPTION
  The shutter for every project's Windows capture scripts. A per-frame script stages
  the window and calls this rather than open-coding a capture, so no project's
  Windows documentation frames can drift in DPI handling or cropping. The helpers
  a capture script needs around it (pointer placement, the frame step) are in
  windows-capture.ps1 beside this file.

  Two things this gets right that a naive capture does not:

  * DPI. PowerShell launches DPI-unaware, so GetWindowRect over a per-monitor-aware
    window returns coordinates divided by the monitor scale -- a 454px window reads
    back 303px and captures blurred and short. The thread is made PerMonitorV2 aware
    before any geometry call.
  * The invisible border. On Windows 10/11 GetWindowRect on a decorated window
    includes roughly 7px of transparent resize margin on three sides. The visible
    frame is DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS), which is what
    -Method Screen crops to.

.PARAMETER Method
  PrintWindow -- asks the window to render itself, so it works while occluded or
  behind another window, and never captures a foreign window that happens to be on
  top. This is the default.

  Screen -- reads the pixels off the desktop after raising the window. Slower and
  it requires an unobstructed desktop, but it is the only way to capture native
  window chrome (title bar, rounded corners, drop shadow) as the user sees it, and
  a WebView2 window under a decorated frame renders more faithfully this way.

  Alpha -- photographs the window twice off the screen, over a black backdrop and
  then a white one, and solves each pixel's colour and coverage. The only method
  that gets a Windows 11 window as it looks -- rounded, antialiased border, and
  transparent outside the corners -- and the only one -Popup works with.

.PARAMETER Popup
  The target is a popup menu (class #32768, opened by TrackPopupMenu, or a
  toolkit's own, such as a WinForms ContextMenuStrip) rather than a window that
  can hold focus. Alpha only, and it changes two things. The raise is
  skipped: a popup never becomes the foreground window, and the ALT press that
  earns foreground rights would dismiss the menu outright. And the backdrops are
  shown without activation, because a menu's modal loop ends the moment anything
  else is activated -- so the capture would photograph two empty backdrops.

.EXAMPLE
  window-shot.ps1 -List
  window-shot.ps1 -ProcessName notepad -TitleLike '*Notepad' -Method Screen -Out shot.png
#>
param(
    [string]$Out,
    [string]$ProcessName,
    [string]$Title,
    [string]$TitleLike,
    [int]$Hwnd = 0,
    [ValidateSet('PrintWindow', 'Screen', 'Alpha')][string]$Method = 'PrintWindow',
    [int]$SettleMs = 500,
    [int]$Width = 0,
    [int]$Height = 0,
    [switch]$Client,
    # Resolve a tie by taking the window highest in z-order, which is the one
    # most recently focused. EnumWindows walks top-down, so that is simply the
    # first match. Only reach for this when the tie is expected and the newest
    # window is the one wanted — two Windows Terminal windows both titled after
    # the tab that was just opened in one of them, say.
    [switch]$First,
    [switch]$Popup,
    [switch]$List
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;

public class WinShot {
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int t, uint flags);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int t, bool repaint);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT val, int size);

    public delegate bool EnumProc(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }

    public const int DWMWA_EXTENDED_FRAME_BOUNDS = 9;
    public const uint PW_RENDERFULLCONTENT = 2;
}
'@

# PerMonitorV2 (-4). Every geometry call below depends on this line.
[void][WinShot]::SetThreadDpiAwarenessContext([IntPtr](-4))

function Get-TopLevelWindows {
    $found = New-Object System.Collections.ArrayList
    $cb = [WinShot+EnumProc] {
        param($h, $p)
        if ([WinShot]::IsWindowVisible($h)) {
            $sb = New-Object System.Text.StringBuilder 512
            [void][WinShot]::GetWindowTextW($h, $sb, $sb.Capacity)
            $text = $sb.ToString()
            if ($text.Length -gt 0) {
                $cls = New-Object System.Text.StringBuilder 256
                [void][WinShot]::GetClassNameW($h, $cls, $cls.Capacity)
                # Not $pid -- that is a read-only automatic variable in PowerShell.
                $owner = 0
                [void][WinShot]::GetWindowThreadProcessId($h, [ref]$owner)
                $r = New-Object WinShot+RECT
                [void][WinShot]::GetWindowRect($h, [ref]$r)
                [void]$found.Add([pscustomobject]@{
                    Hwnd    = $h
                    Title   = $text
                    Class   = $cls.ToString()
                    Pid     = [int]$owner
                    Process = (Get-Process -Id $owner -ErrorAction SilentlyContinue).ProcessName
                    Dpi     = [WinShot]::GetDpiForWindow($h)
                    Rect    = "$($r.Left),$($r.Top) $($r.Right - $r.Left)x$($r.Bottom - $r.Top)"
                })
            }
        }
        return $true
    }
    [void][WinShot]::EnumWindows($cb, [IntPtr]::Zero)
    return $found
}

if ($List) {
    Get-TopLevelWindows | Sort-Object Process, Title | Format-Table -AutoSize Process, Pid, Title, Class, Dpi, Rect
    exit 0
}

if (-not $Out) { throw '-Out is required unless -List is given.' }
# Pin it now, against the caller's working directory. Resolving it later would
# mkdir in one place and save in another.
if (-not [System.IO.Path]::IsPathRooted($Out)) { $Out = Join-Path (Get-Location).ProviderPath $Out }
$Out = [System.IO.Path]::GetFullPath($Out)
if ($Client -and $Method -ne 'PrintWindow') {
    # Silently ignoring it produced a framed capture for a caller that asked for
    # the client area -- a plausible-looking wrong image, which is the one
    # failure mode worth an error.
    throw "-Client only applies to -Method PrintWindow; $Method captures the visible frame. Drop one of the two."
}
if ($Popup -and $Method -ne 'Alpha') {
    throw "-Popup only changes the Alpha path, and -Method is ${Method}: Screen raises the target, whose ALT press dismisses a menu, and PrintWindow has nothing for -Popup to change. Use -Method Alpha."
}

$target = $null
if ($Hwnd -ne 0) {
    $target = [pscustomobject]@{ Hwnd = [IntPtr]$Hwnd; Title = '(by handle)' }
} else {
    $cands = Get-TopLevelWindows
    if ($ProcessName) { $cands = $cands | Where-Object { $_.Process -eq $ProcessName } }
    if ($Title)       { $cands = $cands | Where-Object { $_.Title -eq $Title } }
    if ($TitleLike)   { $cands = $cands | Where-Object { $_.Title -like $TitleLike } }
    $cands = @($cands)
    if ($cands.Count -eq 0) { throw "No window matched (process='$ProcessName' title='$Title$TitleLike'). Run with -List to see what is open." }
    if ($cands.Count -gt 1 -and -not $First) {
        $cands | Format-Table -AutoSize Process, Pid, Title, Rect | Out-String | Write-Host
        throw "$($cands.Count) windows matched -- narrow the filter, or pass -First to take the frontmost."
    }
    $target = $cands[0]
}

$h = [IntPtr]$target.Hwnd
if ([WinShot]::IsIconic($h)) { [void][WinShot]::ShowWindow($h, 9) ; Start-Sleep -Milliseconds 300 }  # SW_RESTORE

if ($Width -gt 0 -and $Height -gt 0) {
    $r0 = New-Object WinShot+RECT
    [void][WinShot]::GetWindowRect($h, [ref]$r0)
    [void][WinShot]::MoveWindow($h, $r0.Left, $r0.Top, $Width, $Height, $true)
    Start-Sleep -Milliseconds 600
}

# Window rect (what PrintWindow draws into) and the visible frame inside it. On
# Windows 10/11 the two differ by the transparent resize margin, so every capture
# is cropped from the first to the second.
$outer = New-Object WinShot+RECT
[void][WinShot]::GetWindowRect($h, [ref]$outer)
$frame = New-Object WinShot+RECT
if ([WinShot]::DwmGetWindowAttribute($h, [WinShot]::DWMWA_EXTENDED_FRAME_BOUNDS, [ref]$frame, 16) -ne 0) { $frame = $outer }

if ($Client) {
    # The app's own pixels and nothing else. An undecorated window still gets a
    # DWM border -- measured 2px, light grey along the top and black on the other
    # three sides at 144 DPI -- which lands in the committed frame as a stray
    # hairline. The client rect excludes it by construction, and unlike a fixed
    # inset it does not need re-deriving on a display at another scale.
    $cr = New-Object WinShot+RECT
    [void][WinShot]::GetClientRect($h, [ref]$cr)
    $origin = New-Object WinShot+POINT
    [void][WinShot]::ClientToScreen($h, [ref]$origin)
    $frame = New-Object WinShot+RECT
    $frame.Left = $origin.X
    $frame.Top = $origin.Y
    $frame.Right = $origin.X + ($cr.Right - $cr.Left)
    $frame.Bottom = $origin.Y + ($cr.Bottom - $cr.Top)
}

$w = $frame.Right - $frame.Left
$t = $frame.Bottom - $frame.Top

# Park the pointer clear of the window: hovering a chart bar or a row raises a
# tooltip that then sits in the committed frame, and the capture cannot see it.
$parkX = if ($frame.Left -gt 60) { $frame.Left - 40 } else { $frame.Right + 40 }
$parkY = $frame.Top + 20
[void][WinShot]::SetCursorPos($parkX, $parkY)

if ($Method -eq 'Alpha') {
    # The only way to get a Windows 11 window as it actually looks -- its border
    # curving round the corners, antialiased, with everything outside the corner
    # transparent so it composites onto whatever colour the docs page is.
    #
    # PrintWindow cannot do it: DWM applies the rounding at composition time, so
    # a PrintWindow surface holds a SQUARE border (measured: two rows of
    # #f3f3f3 straight across the top, including the corner). Masking that to a
    # round shape cuts the border off mid-stroke.
    #
    # So the window is photographed twice off the screen, over a black backdrop
    # and then a white one, and the alpha is solved rather than guessed. For a
    # pixel of colour F and coverage a over backdrop B the screen shows
    # a*F + (1-a)*B, so
    #     black: P0 = a*F                white: P1 = a*F + (1-a)*255
    #     a = 1 - (P1 - P0)/255          F = P0/a
    # which is exact, needs no knowledge of the corner radius, and picks up the
    # real antialiasing instead of a re-drawn approximation.
    Add-Type -AssemblyName System.Windows.Forms

    if (-not $Popup) {
        [void][WinShot]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
        [void][WinShot]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
        [void][WinShot]::BringWindowToTop($h)
        [void][WinShot]::SetForegroundWindow($h)
        $raised = $false
        for ($i = 0; $i -lt 20; $i++) {
            if ([WinShot]::GetForegroundWindow() -eq $h) { $raised = $true; break }
            Start-Sleep -Milliseconds 100
            [void][WinShot]::SetForegroundWindow($h)
        }
        if (-not $raised) { throw 'Could not bring the window to the foreground, so a screen capture would photograph whatever is in front of it. Nothing was written.' }
    }
    [void][WinShot]::DwmGetWindowAttribute($h, [WinShot]::DWMWA_EXTENDED_FRAME_BOUNDS, [ref]$frame, 16)
    $w = $frame.Right - $frame.Left
    $t = $frame.Bottom - $frame.Top

    $pad = 8
    $back = New-Object System.Windows.Forms.Form
    $back.FormBorderStyle = 'None'
    $back.ShowInTaskbar = $false
    $back.TopMost = $true
    $back.StartPosition = 'Manual'

    # How many pixels differ between two captures over the same backdrop. Exact
    # equality, not a tolerance: over a fixed backdrop a still window is
    # bit-identical, so any difference at all is something having moved.
    function Get-MovedMask($a, $b) {
        $r = New-Object System.Drawing.Rectangle 0, 0, $a.Width, $a.Height
        $lo = [System.Drawing.Imaging.ImageLockMode]::ReadOnly
        $pf = [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
        $da = $a.LockBits($r, $lo, $pf); $db = $b.LockBits($r, $lo, $pf)
        try {
            $n = $da.Stride * $a.Height
            $xa = New-Object byte[] $n; $xb = New-Object byte[] $n
            [System.Runtime.InteropServices.Marshal]::Copy($da.Scan0, $xa, 0, $n)
            [System.Runtime.InteropServices.Marshal]::Copy($db.Scan0, $xb, 0, $n)
            $mask = New-Object bool[] ($n / 4)
            $count = 0
            for ($i = 0; $i -lt $n; $i += 4) {
                if ($xa[$i] -ne $xb[$i] -or $xa[$i + 1] -ne $xb[$i + 1] -or $xa[$i + 2] -ne $xb[$i + 2]) {
                    $mask[$i / 4] = $true; $count++
                }
            }
            return @{ Count = $count; Bits = $mask }
        } finally { $a.UnlockBits($da); $b.UnlockBits($db) }
    }

    function Get-Over([System.Drawing.Color]$colour) {
        $back.BackColor = $colour
        # Behind a popup, the SetWindowPos below shows the backdrop on its own,
        # with SWP_NOACTIVATE; Show() would activate it and end the menu.
        if (-not $Popup) { $back.Show() }
        # SWP_NOACTIVATE|SWP_SHOWWINDOW: insert the backdrop directly BELOW the
        # target in z-order, which is what keeps a topmost target (an
        # always-on-top window or a menu) visible over a topmost backdrop, and
        # keeps focus put.
        [void][WinShot]::SetWindowPos($back.Handle, $h, $frame.Left - $pad, $frame.Top - $pad, $w + 2 * $pad, $t + 2 * $pad, 0x0010 -bor 0x0040)
        $back.Refresh()
        [System.Windows.Forms.Application]::DoEvents()
        # Deliberately short, and not $SettleMs. Only the backdrop has to repaint
        # and be composited -- about six frames at 60Hz is ample -- while every
        # millisecond spent here widens the window in which a ticking clock can
        # move between exposures and force a re-shoot.
        Start-Sleep -Milliseconds 100
        $b = New-Object System.Drawing.Bitmap $w, $t, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $gg = [System.Drawing.Graphics]::FromImage($b)
        $gg.CopyFromScreen($frame.Left, $frame.Top, 0, 0, (New-Object System.Drawing.Size $w, $t))
        $gg.Dispose()
        return $b
    }

    # Anything that moves BETWEEN the two exposures is solved as a translucent
    # blend of its two states -- a row's elapsed-time counter ticking over left a
    # ghosted digit in a committed hero. So the window is photographed over black
    # twice, either side of the white one, and the pair must agree: a difference
    # means something on screen moved and the solve for those pixels is a
    # fiction. Retried rather than reported, because a one-second tick landing
    # inside a ~150ms window is uncommon and simply shooting again clears it.
    $onBlack = $null; $onWhite = $null; $movedMask = $null
    try {
        $best = $null
        for ($try = 1; $try -le 3; $try++) {
            $b1 = Get-Over ([System.Drawing.Color]::Black)
            $wh = Get-Over ([System.Drawing.Color]::White)
            $b2 = Get-Over ([System.Drawing.Color]::Black)
            $mask = Get-MovedMask $b1 $b2
            if ($mask.Count -le 0) {
                $onBlack = $b1; $onWhite = $wh; $b2.Dispose(); $movedMask = $mask
                break
            }
            Write-Host "  attempt ${try}: $($mask.Count) pixels moved between exposures"
            if ($best) { $best.b1.Dispose(); $best.wh.Dispose() }
            $best = @{ b1 = $b1; wh = $wh; mask = $mask }
            $b2.Dispose()
            Start-Sleep -Milliseconds 700
        }

        if (-not $onBlack) {
            # Something on the window animates continuously and no pair will ever
            # agree -- a status badge that pulses by design, in a frame whose
            # point is to show it. Rather than ship a
            # blend of two frames or refuse a frame that can never be taken, the
            # moving pixels are taken OPAQUE from one exposure. That is correct
            # for them: they are interior pixels of a window, where the true
            # alpha is 255 and only the colour was in doubt. Partial alpha lives
            # at the border and the corners, which do not animate.
            $frac = $best.mask.Count / [double]($w * $t)
            if ($frac -gt 0.20) {
                throw "$([int]($frac * 100))% of the window changed between exposures -- that is the window moving or redrawing, not an animation, and every alpha would be a blend. Nothing was written."
            }
            $onBlack = $best.b1; $onWhite = $best.wh; $movedMask = $best.mask
            Write-Host "  $($movedMask.Count) animating pixels taken opaque from a single exposure"
        }
    } finally {
        $back.Close()
        $back.Dispose()
    }

    # The solve runs over raw bytes rather than GetPixel/SetPixel: for a
    # 2284x1097 window the managed per-pixel API would be five million calls and
    # takes minutes where this takes under a second.
    $bmp = New-Object System.Drawing.Bitmap $w, $t, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $rect = New-Object System.Drawing.Rectangle 0, 0, $w, $t
    $ro = [System.Drawing.Imaging.ImageLockMode]::ReadOnly
    $rw = [System.Drawing.Imaging.ImageLockMode]::WriteOnly
    $fmt = [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
    $d0 = $onBlack.LockBits($rect, $ro, $fmt)
    $d1 = $onWhite.LockBits($rect, $ro, $fmt)
    $dd = $bmp.LockBits($rect, $rw, $fmt)
    try {
        $n = $dd.Stride * $t
        $b0 = New-Object byte[] $n
        $b1 = New-Object byte[] $n
        $bo = New-Object byte[] $n
        [System.Runtime.InteropServices.Marshal]::Copy($d0.Scan0, $b0, 0, $n)
        [System.Runtime.InteropServices.Marshal]::Copy($d1.Scan0, $b1, 0, $n)
        for ($i = 0; $i -lt $n; $i += 4) {
            if ($movedMask.Bits[$i / 4]) {
                # Animating: opaque, colour straight off the black exposure.
                $bo[$i] = $b0[$i]; $bo[$i + 1] = $b0[$i + 1]; $bo[$i + 2] = $b0[$i + 2]; $bo[$i + 3] = 255
                continue
            }
            # BGRA. One alpha per pixel, taken from the channel with the most
            # signal so a saturated colour cannot skew it.
            $db = $b1[$i] - $b0[$i]
            $dg = $b1[$i + 1] - $b0[$i + 1]
            $dr = $b1[$i + 2] - $b0[$i + 2]
            $d = $db; if ($dg -gt $d) { $d = $dg }; if ($dr -gt $d) { $d = $dr }
            if ($d -lt 0) { $d = 0 }
            $a = 255 - $d
            if ($a -le 0) { continue }        # already zeroed: fully transparent
            $f = 255.0 / $a
            $vb = [int]($b0[$i] * $f); if ($vb -gt 255) { $vb = 255 }
            $vg = [int]($b0[$i + 1] * $f); if ($vg -gt 255) { $vg = 255 }
            $vr = [int]($b0[$i + 2] * $f); if ($vr -gt 255) { $vr = 255 }
            $bo[$i] = [byte]$vb
            $bo[$i + 1] = [byte]$vg
            $bo[$i + 2] = [byte]$vr
            $bo[$i + 3] = [byte]$a
        }
        [System.Runtime.InteropServices.Marshal]::Copy($bo, 0, $dd.Scan0, $n)
    } finally {
        $onBlack.UnlockBits($d0)
        $onWhite.UnlockBits($d1)
        $bmp.UnlockBits($dd)
    }
    $onBlack.Dispose()
    $onWhite.Dispose()
} elseif ($Method -eq 'Screen') {
    # Windows refuses SetForegroundWindow from a process that has not recently
    # had input, and it refuses it SILENTLY -- returning false and leaving the
    # desktop where it was. Reading the screen then captures whatever is at
    # those coordinates, which is how this produced a frame of wallpaper that
    # looked like a capture. Synthesising a harmless key press satisfies the
    # foreground rule, and the result is asserted rather than assumed.
    [void][WinShot]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)          # ALT down
    [void][WinShot]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)          # ALT up
    [void][WinShot]::BringWindowToTop($h)
    [void][WinShot]::SetForegroundWindow($h)
    $raised = $false
    for ($i = 0; $i -lt 20; $i++) {
        if ([WinShot]::GetForegroundWindow() -eq $h) { $raised = $true; break }
        Start-Sleep -Milliseconds 100
        [void][WinShot]::SetForegroundWindow($h)
    }
    if (-not $raised) { throw 'Could not bring the window to the foreground, so a screen capture would photograph whatever is in front of it. Nothing was written.' }

    $bmp = New-Object System.Drawing.Bitmap $w, $t, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    Start-Sleep -Milliseconds $SettleMs
    # The window may have moved while being raised.
    [void][WinShot]::DwmGetWindowAttribute($h, [WinShot]::DWMWA_EXTENDED_FRAME_BOUNDS, [ref]$frame, 16)
    $g.CopyFromScreen($frame.Left, $frame.Top, 0, 0, (New-Object System.Drawing.Size $w, $t))
    $g.Dispose()
} else {
    Start-Sleep -Milliseconds $SettleMs
    # PrintWindow only ever draws at the window rect's origin, so capture the
    # whole rect and crop the margin off afterwards rather than trying to offset
    # the destination -- a GDI+ world transform does not survive GetHdc().
    $full = New-Object System.Drawing.Bitmap ($outer.Right - $outer.Left), ($outer.Bottom - $outer.Top), ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($full)
    $hdc = $g.GetHdc()
    $ok = [WinShot]::PrintWindow($h, $hdc, [WinShot]::PW_RENDERFULLCONTENT)
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    if (-not $ok) { $full.Dispose(); throw 'PrintWindow refused the window. Try -Method Screen.' }
    $crop = New-Object System.Drawing.Rectangle ($frame.Left - $outer.Left), ($frame.Top - $outer.Top), $w, $t
    $bmp = $full.Clone($crop, $full.PixelFormat)
    $full.Dispose()
}

$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
# Record the window's DPI in the PNG. The frame the docs-relevance skill's
# winframe.py draws is sized from it, and nothing else in the file says which
# display the window was on.
$shotDpi = [WinShot]::GetDpiForWindow($h)
if ($shotDpi -gt 0) { $bmp.SetResolution($shotDpi, $shotDpi) }
# Saved untouched, the compositor's drop shadow included: the two-exposure solve
# recovers it outside the corners because it is genuinely on screen. Nothing here
# clears it: a caller that wants a frame hands the file to Add-WindowFrame in
# windows-capture.ps1, which draws everything outside the content Windows clips
# and keeps this file as the raw.
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "$Out  $($bmp.Width)x$($bmp.Height)  dpi=$([WinShot]::GetDpiForWindow($h))  method=$Method  title='$($target.Title)'"
$bmp.Dispose()
