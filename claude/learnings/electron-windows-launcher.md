# Launching Electron Widgets Silently on Windows

How to launch an Electron tray/widget app from the Startup folder or a double-click without a console window flashing, and how to avoid the BrowserWindow being stuck hidden along that launch path.

## Why not `.bat` / `.cmd`

Batch files always spawn a visible `cmd.exe` window when double-clicked or launched from Startup. `start /min` and `/b` mitigate but don't eliminate the flash, and Startup-folder launches keep the console visible in the background for the whole session. Bad UX for apps you want to run silently on login.

## Why not PowerShell

PowerShell scripts flash `powershell.exe` briefly before `-WindowStyle Hidden` takes effect, and Windows doesn't associate `.ps1` with execution by default — double-clicking opens Notepad.

## Why not a `.lnk` shortcut

Shortcut files can set "Run: Minimized" but that minimizes to the taskbar, doesn't hide. Also `.lnk` is binary and ugly in git.

## Why VBScript wins

VBScript's `WshShell.Run` takes a window-state flag that applies to the child process from the moment it's spawned. No flash, no console, text-file source-controllable, ships on every Windows box.

```vbscript
' launch.vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "node_modules\electron\dist\electron.exe src\widget.cjs", 0, False
```

- Second arg `0` = `SW_HIDE`. Hides the child's initial console window (and propagates down via STARTUPINFO).
- Third arg `False` = don't wait for the child to exit (fire-and-forget).
- Setting `CurrentDirectory` first lets the `Run` command use relative paths to the project.

## The BrowserWindow-stuck-hidden gotcha

When the parent process is launched with `SW_HIDE` via wscript, Windows fills the child's `STARTUPINFO.wShowWindow` field. Electron sometimes inherits this and applies it to the first `BrowserWindow` — result: the widget never appears on launch; the user has to click the tray icon to reveal it.

Electron's documented "Show window gracefully" pattern alone is not enough under wscript:

```js
const win = new BrowserWindow({ show: false });
win.once('ready-to-show', () => win.show());  // may not fire first
```

Empirical data from a real repo (logged to disk via a temporary debug logger): under wscript launch, `did-finish-load` fires **~100 ms before** `ready-to-show`. Under a direct `electron <main>` launch, `ready-to-show` fires first. Either event can win, and whichever fires first needs to trigger the show.

## The fix

Listen on both events; whichever fires first shows the window, the other becomes a no-op via `isVisible()` guard:

```js
win = new BrowserWindow({
  // ...
  show: false,
  // ...
});

win.loadFile(/* ... */);
const revealWhenReady = () => {
  if (win && !win.isVisible()) {
    win.show();
    win.moveTop();
  }
};
win.once("ready-to-show", revealWhenReady);
win.webContents.once("did-finish-load", revealWhenReady);
```

`moveTop()` matters: in some launch contexts `show()` alone places the window behind others in the Z-order. `moveTop()` forces it to the top.

## Diagnostic technique

If a future Electron launch scenario fails this way, instrument both events (plus a `setTimeout` fallback) with a disk logger that records `event`, `visible`, `timestamp`. The log lets you see which event path is actually working. Once the fix is confirmed, strip the diagnostic to the minimum two listeners.

## Notes

- Microsoft has marked VBScript deprecated starting Windows 11 24H2. Still available as an optional Windows feature; slated for full removal in a future release. Long-term replacements: a tiny compiled launcher (Rust/C#), or a Scheduled Task with a hidden action.
- The VBScript `Run` flag `0` is distinct from Windows API `SW_HIDE` — VBScript maps several of its numeric flags onto WinAPI constants. `0` is the one that translates to hidden.
