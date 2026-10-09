# Starting a desktop app on the user's behalf on Windows

A background agent that starts an app for the user (a torrent client, a VPN) has to do two things: start it without taking over the desktop, and know whether it is already running so it never starts a second copy. Neither works the obvious way. `std::process::Command` cannot ask for a minimized window. And the program the user points at is often a launcher that exits, while the app that stays running has a different exe in a different folder.

## Start it minimized without focus

Call `CreateProcessW` directly with a `STARTUPINFOW` that sets `dwFlags = STARTF_USESHOWWINDOW` and `wShowWindow = SW_SHOWMINNOACTIVE`. Windows passes that value to the app's first `ShowWindow(SW_SHOWDEFAULT)` call, so the main window opens minimized in the taskbar and the foreground window keeps focus. Verified 2026-10-09 with qBittorrent 5.1.0, a Qt app whose own setting opens its main window normally at startup: it opened minimized. Rust's `Command` exposes creation flags but not `wShowWindow`, so this needs `windows-sys` (`Win32_System_Threading`, `Win32_UI_WindowsAndMessaging`, `Win32_Foundation`, `Win32_Security`).

The flags around it:

- **`CREATE_NO_WINDOW`** makes no difference to a GUI exe, but it stops a console stand-in used in tests (`whoami.exe`, `where.exe`) from flashing a console.
- **`CREATE_BREAKAWAY_FROM_JOB`** lets the app outlive a launcher that runs inside a kill-on-close job object. Some terminals and IDEs create such jobs. A job that forbids breakaway refuses the call with `ERROR_ACCESS_DENIED`, so retry once without the flag.
- **`ERROR_ELEVATION_REQUIRED` (740)** means the exe's manifest or compatibility setting asks for administrator rights. `CreateProcessW` cannot elevate, so report it as its own failure ("set to run as administrator") rather than as a generic one.
- **The process handle** is how to tell a crash from a hand-over: `WaitForSingleObject` with a timeout, then `GetExitCodeProcess`. A launcher that hands over to a running instance usually exits 0. Close the thread handle at once and the process handle on drop.

On macOS the equivalent is `/usr/bin/open -g -j -a <bundle>` (do not activate, launch hidden). Unverified there.

## Know whether it already runs

Match running processes by exe path, never by process name alone. A name says nothing about which install, and another user's session can run the same name. Two match rules cover the cases:

- **The exe itself**, for an app that is its own program (qBittorrent): canonicalise both paths and compare them case-insensitively.
- **Any process in the user's own session whose exe sits in the program's folder or below it**, for an app reached through a launcher. Proton VPN is the worked case. Its program is `C:\Program Files\Proton\VPN\ProtonVPN.Launcher.exe`, which exits once it has started the app. What stays running is `v5.1.8\ProtonVPN.Client.exe` under the same folder, in the user's session, with a versioned subfolder that changes on update. Its services `ProtonVPNService.exe`, `ProtonVPN.NrptWatchdog.exe` and `ProtonVPN.WireGuardService.exe` run under the same folder in session 0 whether the app is open or not. The session filter is what keeps them from reading as "running".

Never use the folder rule for a program in a shared folder such as `System32` or a tools directory: every process there would count as the app.

The `sysinfo` crate gives both the exe path and `Process::session_id()`, which calls `ProcessIdToSessionId`. Request exe paths explicitly (`ProcessRefreshKind::nothing().with_exe(UpdateKind::OnlyIfNotSet)`). For processes another account owns, such as services, it returns no exe at all. For the user's own processes it returns the full path, elevated ones included. Measured 2026-10-09: across 446 same-user processes no exe came back empty, and only other accounts' processes came back `None`.

## Telling "not running" from "running but not answering"

When an app's local API refuses the connection, a process scan by name separates the two: no `qbittorrent.exe` means not running, and a running one means its web UI is off. That is the one place a name match is fine, because the question is "is any copy up" rather than "is this install up".
