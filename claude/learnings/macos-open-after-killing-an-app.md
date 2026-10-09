# macOS: relaunching an app you just killed

A deploy that stops an app, replaces its bundle and starts it again has to wait for the old process to be gone, because `open` misreports the launch in both directions while that process is still terminating. The signal returning is not the exit, and the launcher's exit status is not a running app.

## What open does while the old instance is dying

Measured 2026-10-09 on macOS 27, against a signalled app that takes 300 ms to exit:

| When `open` runs | Exit status | Result |
|---|---|---|
| while the old pid is alive | 0 | activates the dying instance; nothing is running afterwards |
| after the old pid is gone | 0 | the new build starts |

The first row is the expensive one. The status says success, the new build is installed, and the process table is empty two seconds later — so a deploy reading that status reports success on an app that is not running.

The same race also lands as `_LSOpenURLsWithCompletionHandler() failed with error -600.` (-600 is `procNotFound`), exit 1, on a request LaunchServices went on to honour: observed on a tauri-dashboard deploy the same day, where `set -e` aborted the script on that status while the new binary was running two seconds later. A non-zero `open` is no more evidence of a failed launch than a zero one is of a successful one.

## What to do instead

Poll for the process to disappear after the kill, bounded, with a force-kill at the end of the grace; then confirm the launch against the process table rather than the launcher's status. Both waits live in `claude/skills/shared/app-process.sh`, sourced by the deploy and cleanup targets that stop a desktop app. A removal races the same way a relaunch does: `rm -rf` over a bundle whose process is still running unmaps the binary under it.

## Reproducing it without taking the screen

A bundle whose `Info.plist` sets `LSUIElement` and `LSBackgroundOnly` launches through LaunchServices with no window and no focus change, so the race can be driven over and over without touching what the user is doing. Two things the harness needs: a real compiled binary as the bundle executable, since a shell script there gives the process the name `bash` and `pgrep -x <app>` never matches it; and an ad-hoc signature (`codesign --force --sign -`), which is enough for a local launch.
