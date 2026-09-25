<#
  Helpers for a project's Windows capture scripts, beside window-shot.ps1.

  Dot-source it from docs/screenshots/capture/<id>.ps1:

      . (Join-Path $env:USERPROFILE '.claude\skills\docs-relevance\scripts\windows-capture.ps1')

  What lives here is what any project needs unchanged: the primary work area,
  pointer placement, finding a process's windows, posting one a message, the
  shutter and the frame step. Which window to open and what state to stage stays
  in the project's own script.

  A SCRIPT THAT DOTS THIS FILE DECLARES [CmdletBinding()]. Without it a simple
  param block is not strict: PowerShell drops an argument the script does not
  declare into $args silently, so a mistyped flag is accepted, ignored, and the
  capture runs anyway -- taking the machine over and overwriting a committed frame.

  SAVE EVERY .ps1 AS UTF-8 WITH A BOM. Windows PowerShell reads one without a BOM
  as ANSI, so a single non-ASCII character -- an em dash in a comment is enough --
  becomes two bytes that break the parse somewhere else entirely.
#>

if (-not ('WinCapture' -as [type])) {
    Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinCapture {
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
    [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
    public delegate bool EnumProc(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
'@
}

# The top-level windows of one process whose class matches -Class, a -like
# pattern, so an exact class name works too. Hidden windows count unless
# -VisibleOnly is given: a tray icon's message window is hidden, its menu is not.
function Find-ProcessWindows {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$Class,
        [switch]$VisibleOnly
    )
    $found = New-Object System.Collections.ArrayList
    $cb = [WinCapture+EnumProc] {
        param($h, $p)
        # Not $pid -- that is a read-only automatic variable in PowerShell.
        $owner = 0
        [void][WinCapture]::GetWindowThreadProcessId($h, [ref]$owner)
        if ($owner -eq $ProcessId -and (-not $VisibleOnly -or [WinCapture]::IsWindowVisible($h))) {
            $sb = New-Object System.Text.StringBuilder 256
            [void][WinCapture]::GetClassNameW($h, $sb, $sb.Capacity)
            if ($sb.ToString() -like $Class) { [void]$found.Add($h) }
        }
        return $true
    }
    [void][WinCapture]::EnumWindows($cb, [IntPtr]::Zero)
    return @($found)
}

# Coordinates are physical pixels. Get-PrimaryWorkArea returns the rectangle to
# aim at in the same units: the thread is made PerMonitorV2 aware first, or a
# scaled display reports its work area divided by its scale.
function Get-PrimaryWorkArea {
    Add-Type -AssemblyName System.Windows.Forms
    [void][WinCapture]::SetThreadDpiAwarenessContext([IntPtr](-4))
    return [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
}

# Move the pointer to (X, Y) for as long as -Do runs and put it back afterwards,
# whatever -Do does. A tray menu opens at the pointer, and a window that opens
# under a resting pointer shows its hover tooltip, which moving the pointer away
# afterwards does not clear.
function Invoke-WithPointerAt {
    param(
        [Parameter(Mandatory = $true)][int]$X,
        [Parameter(Mandatory = $true)][int]$Y,
        [Parameter(Mandatory = $true)][scriptblock]$Do
    )
    [void][WinCapture]::SetThreadDpiAwarenessContext([IntPtr](-4))
    $was = New-Object WinCapture+POINT
    [void][WinCapture]::GetCursorPos([ref]$was)
    [void][WinCapture]::SetCursorPos($X, $Y)
    try { & $Do } finally { [void][WinCapture]::SetCursorPos($was.X, $was.Y) }
}

# Takes a hashtable and splats it, rather than collecting remaining arguments:
# with -ValueFromRemainingArguments PowerShell resolves `-Out` against its own
# common parameters first and fails on the ambiguity with -OutVariable.
function Invoke-WindowShot {
    param([Parameter(Mandatory = $true)][hashtable]$Params)
    & (Join-Path $PSScriptRoot 'window-shot.ps1') @Params
}

# Draw a saved frame's Windows 11 frame again, from Windows' own model.
#
# A captured Windows frame cannot be kept or cleaned: its border is translucent, so
# it arrives mixed with the drop shadow and the backdrop behind it (the lighter-top,
# darker-bottom shading a captured border shows is the shadow, not the border).
# winframe.py beside this file keeps only the content inside the clip Windows
# applies and draws the frame from DWM's measured model: 8 DIP corners (4 for a
# menu) flattened into chords, a 1 px antialiasing ramp, a 2 px border at 144 DPI.
# Drawn with Windows' own border and the window's own shadow it reproduces a real
# capture to under one level RMS. It is Python so the macOS half of a project can
# call the same one.
#
# THE RING IS LIGHTER THAN WINDOWS' AND THERE IS NO SHADOW, chosen by eye on
# 2026-09-24. Windows' own border, rgba(117,117,117,0.40), reads 200 on a white
# page and 55 on GitHub's dark one, where a README renders for a dark-mode reader.
# rgba(146,146,146,0.69) reads 180 and 105 on every side. The shadow is left out
# because it is what makes the bottom of a captured border darker than its top.
#
# -Kind menu gives a menu's own shape, 4 DIP corners, rather than a window's.
# -Cut names the sides of a crop that are cuts rather than the window's edges: they
# get the border straight along them and square corners.
#
# The capture records its window's DPI in the PNG and winframe.py sizes the frame
# from it. This runs once, on the raw capture; a copy of that raw is kept first.
$WindowFrameRing = '929292:0.69'
function Add-WindowFrame {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [ValidateSet('window', 'menu')][string]$Kind = 'window',
        [ValidateSet('left', 'top', 'right', 'bottom')][string[]]$Cut = @()
    )
    $winframe = Join-Path $PSScriptRoot 'winframe.py'
    $py = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
          elseif (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
          else { $null }
    # THE FLAGS ARE BUILT ONCE AND USED FOR BOTH THE CALL AND THE SUGGESTED REMEDY,
    # so the command a failure tells you to run is the one that failed.
    $flags = @('--kind', $Kind, '--shadow', 'none', '--ring', $WindowFrameRing)
    if ($Cut.Count -gt 0) { $flags += @('--cut', ($Cut -join ',')) }
    # KEEP THE RAW, and before anything can throw. The frame step rewrites the file
    # in place, so without a copy the only way to try a different frame is to take
    # the shot again -- which needs the app staged and the machine taken over. And a
    # caller that stages its file in a temp directory deletes it in `finally`, so a
    # guard that threw first would lose the capture outright. That is why the repo
    # is found from the script that called this, never from $Path, which may be that
    # temp directory: the copy goes to the gitignored tmp/ of the caller's repo.
    # The probe runs with Continue: under Windows PowerShell 5.1 a caller's
    # $ErrorActionPreference = 'Stop' turns git's stderr into a terminating error
    # that would pre-empt the message below.
    $caller = $MyInvocation.PSScriptRoot
    $root = if ($caller) { & { $ErrorActionPreference = 'Continue'; git -C $caller rev-parse --show-toplevel 2>$null } }
    if (-not $root) { throw "Add-WindowFrame was called from outside a git repository, so there is no tmp/ to keep the raw of $Path in, and it has no frame. Call it from a capture script under the repo's docs/screenshots/capture/." }
    $raws = Join-Path $root 'tmp\screenshot-raws'
    New-Item -ItemType Directory -Force -Path $raws | Out-Null
    $raw = Join-Path $raws (Split-Path -Leaf $Path)
    Copy-Item -Force $Path $raw
    $suggest = "$(if ($py) { $py } else { 'python' }) `"$winframe`" $($flags -join ' ') `"$raw`" --out `"$Path`""
    if (-not $py) { throw "Captured $Path but python is not on PATH, so it has no frame. The capture is kept at $raw. Install python (with numpy and scipy) and run: $suggest" }
    if (-not (Test-Path $winframe)) { throw "Captured $Path but $winframe is missing, so it has no frame. The capture is kept at $raw. Install the dotfiles and run: $suggest" }
    & $py $winframe @flags $Path
    if ($LASTEXITCODE -ne 0) { throw "winframe.py failed on $Path; the frame was not drawn. The capture is kept at $raw. Reproduce with: $suggest" }
}
