# Windows: stopping and relaunching an app from a deploy script

A deploy that kills an app, replaces its files and starts it again asks two questions of the process table: is the old instance gone, and did the new one start. On Windows the answers come back faster than on macOS (`macos-open-after-killing-an-app.md`), and that speed is what makes the obvious launch check wrong.

## The launch check has to outlast startup

`Start-Process`, like `CreateProcess` underneath it, returns after the process exists. So a check that polls until the process appears passes on its first poll, about 0.4 s after launch, for an app that crashes a second later. The check needs to see the process twice: once to know it appeared, and again after a survival window to know it stayed.

Measured 2026-10-09 with a hidden stand-in exe that exits about a second after launch:

| Check | Verdict on the dying exe |
|---|---|
| poll until it appears | passed 2 of 3 |
| fixed 2 s sleep, then one `Get-Process` | failed 3 of 3 |
| poll until it appears, then still there 2 s later | failed 5 of 5 |

A long-lived process passed the last check and a never-launched one failed it. The same reasoning applies on Linux, where a backgrounded exec exists before the shell moves on. `wait_for_app_start` in `claude/skills/shared/app-process.sh` implements the last row for every platform.

A process probe through `powershell.exe -Command "Get-Process …"` costs about 1 s on a cold start and 0.35 s once warm. That cost is part of every poll interval and can swallow a short-lived process before the first poll sees it, which is why the first trial in the table above failed both checks.

## The stop path showed no lock in what was measured

`Stop-Process -Force` does not wait for the process to finish exiting. Deleting the exe straight afterwards, as the deploy and cleanup targets do, never hit a sharing violation in what was measured on 2026-10-09:

- 30 of 30 with a small console exe, killed and deleted in a tight loop.
- 1 real deploy of a .NET tray app, whose install step deletes the old files right after the kill.

A Tauri app, with WebView2 children and a larger working set, is still unmeasured. A failure there would abort the deploy under `set -e`, and re-running recovers it.

## Reproducing it without taking the screen

Copy a console exe from System32 under a distinct name, so `Get-Process <name>` matches only the copy, and start it from Python with `CREATE_NO_WINDOW`. Nothing appears on the desktop. A copy of `PING.EXE` run as `<name> -n <count> 127.0.0.1` lives for about `count - 1` seconds, which gives a crash at any chosen moment.
