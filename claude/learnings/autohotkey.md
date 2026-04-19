# AutoHotkey Learnings

Practical patterns for AutoHotkey v2 scripts on Windows. Everything here is general-purpose — project-specific script details stay in the project's own docs.

## Conventions

- **AutoHotkey v2** (`#Requires AutoHotkey v2.0`) — v1 syntax is incompatible and should not be mixed.
- Use `#SingleInstance Force` in runtime scripts so re-running reloads instead of spawning duplicates.
- Use `Persistent` for scripts that only install timers/hooks and would otherwise exit after their initial run.
- Set `A_IconTip := "..."` for tray identification — makes it easy to tell multiple AHK processes apart in the tray.
- `SetTitleMatchMode(2)` enables partial title matching, which is more robust than exact matches for windows whose titles change (e.g. document editors).

## Hiding Windows from the Taskbar

Toggling the `WS_EX_TOOLWINDOW` extended style (`0x80`) removes a window from the taskbar and Alt+Tab without affecting its visibility. The style change only takes effect while the window is hidden, so the sequence is: `WinHide` → `WinSetExStyle("+0x80", win)` → `WinShow` → `WinActivate`.

Detect new windows via the shell hook instead of polling:

```ahk
SHELLHOOK := DllCall("RegisterWindowMessage", "Str", "SHELLHOOK")
DllCall("RegisterShellHookWindow", "Ptr", A_ScriptHwnd)
OnMessage(SHELLHOOK, OnShellMessage)

OnShellMessage(wParam, lParam, msg, hwnd) {
    static HSHELL_WINDOWCREATED := 1
    if (wParam = HSHELL_WINDOWCREATED) {
        SetTimer(() => HandleWindow(lParam), -100)  ; small delay for window to initialize
    }
}

OnExit((reason, code) => DllCall("DeregisterShellHookWindow", "Ptr", A_ScriptHwnd))
```

The `-100` SetTimer runs once after 100ms; matters because fresh windows often haven't set their final title/class at creation time.

## Folder Watch Pattern

Timestamp-based detection avoids maintaining a set of known filenames:

```ahk
global lastTimestamp := A_Now
SetTimer(Check, 500)

Check() {
    global lastTimestamp
    loop files watchFolder "\*.*" {
        if (A_LoopFileTimeCreated > lastTimestamp) {
            lastTimestamp := A_LoopFileTimeCreated
            ; act on A_LoopFileFullPath
        }
    }
}
```

Advance `lastTimestamp` inside the loop (not after it) so multiple new files in the same tick each trigger. Use `EnvGet("SOMETHING_DIR")` to make the watched folder configurable without editing the script.

## Windows Auto-Start

Startup folder: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`

**Use a `.lnk` shortcut, not a symlink.** Two traps:
- `ln -s` from Git Bash on Windows silently creates a **copy**, not a symlink. The script runs on startup but edits to the source don't propagate.
- `cmd /c mklink` needs an Administrator prompt.

Create the shortcut via PowerShell (not an admin prompt):

```powershell
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\<name>.ahk.lnk")
$sc.TargetPath = "<absolute path to .ahk file>"
$sc.Save()
```

Naming the shortcut `<name>.ahk.lnk` (keeping the `.ahk` in the stem) makes it clear in the Startup folder what kind of script it runs.

From Git Bash on Windows, wrap the PowerShell command in `powershell.exe -Command '...'` with single quotes outside, double inside.
