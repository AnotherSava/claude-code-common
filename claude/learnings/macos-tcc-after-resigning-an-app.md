# Privacy grants after an app's signature changes

Replacing a Developer-ID-signed app with an ad-hoc build of the same bundle identifier does not
*deny* its privacy permissions. It leaves some services holding no decision at all, and a missing
decision repairs itself with a prompt. Reaching for `tccutil reset` first destroys the grants that
survived. Measured 2026-10-04 on macOS 27.0.1, replacing a notarized `com.umputun.agterm` with an
ad-hoc Release build of the same id.

## What survived and what did not

| Service | State after the swap | How it was decided |
|---|---|---|
| Apple Events | authorized | `osascript -e 'tell application "Finder" to get version'` exited 0 in 0.05s; System Events in 0.44s |
| Microphone | no stored row | `authorizationStatus` was `notDetermined`; one `requestAccess` returned true and the row became `authorized` |
| Camera, Contacts, Calendars, Reminders, Photos, Location | no stored row | read directly, nothing prompted |

Sub-second is the tell for a stored row: macOS answered from the database with no dialog, so those
Apple Events grants matched the new signature. Nothing was left *denying*, so `tccutil reset` had
nothing to repair.

## `tccutil reset` removes a decision rather than fixing one

Its man page is the whole argument: reset "causes apps to prompt again the next time they access the
service." So resetting a service whose grant still works costs that grant and buys a prompt.

Two further hazards:

- **Omitting the bundle identifier widens it to every app.** `tccutil reset Accessibility` resets
  the service machine-wide; only `tccutil reset Accessibility com.example.app` is scoped.
- **`reset All <bundle-id>` is the sledgehammer** and fails for the same reason — it discards the
  rows that matched.

Reach for it only when a service denies while System Settings still shows its switch on.

## The unified log is not a usable instrument for this

```bash
log show --predicate 'subsystem == "com.apple.TCC"' --last 40m --info --debug   # 0 lines
log show --predicate 'process == "tccd"' --last 40m --info --debug              # 0 lines
```

Both returned nothing over a window containing real TCC activity, while `pgrep -xl tccd` showed two
running processes. Neither the subsystem nor the process predicate yields entries on macOS 27, so a
plan that says "watch the TCC log for denials" has no instrument behind it.

Both TCC databases also refuse a shell without Full Disk Access — `sqlite3
~/Library/Application\ Support/com.apple.TCC/TCC.db` answers `authorization denied` or `unable to
open database file` — so the rows cannot be enumerated that way either.

## Read the stored decisions through the frameworks, which prompt nothing

Every relevant framework exposes a status getter that reads the decision without requesting it. A
single-file `swift` script is enough:

```swift
import AVFoundation; import Contacts; import CoreLocation
import EventKit; import Photos; import ApplicationServices

print(AVCaptureDevice.authorizationStatus(for: .audio).rawValue)   // 0 notDetermined, 3 authorized
print(CNContactStore.authorizationStatus(for: .contacts).rawValue)
print(EKEventStore.authorizationStatus(for: .event).rawValue)
print(PHPhotoLibrary.authorizationStatus(for: .readWrite).rawValue)
print(CLLocationManager().authorizationStatus.rawValue)
print(AXIsProcessTrusted())
```

Run it with `swift <file>.swift`. To settle whether a grant merely lacks a row or actively denies,
call `requestAccess` with a semaphore and time it: sub-second means a stored row answered, seconds
mean a dialog was involved.

**A probe run from a terminal pane reads the hosting app's TCC subject, not its own.** The
microphone grant this probe requested appeared in System Settings under the terminal app, which is
what confirms the whole table describes the app rather than the probe binary.

## Accessibility is the exception and says nothing about the parent

`AXIsProcessTrusted()` is per-process, so an unbundled helper reports untrusted however the hosting
app is configured. Before treating a `false` as a lost grant, check whether the app asks for
Accessibility at all — an app registering a global hotkey through Carbon's `RegisterEventHotKey`
needs no grant, while `NSEvent.addGlobalMonitorForEvents` does.

## An ad-hoc build carries `get-task-allow`, which a notarized one does not

```bash
codesign -d --entitlements - --xml /Applications/<app>.app | plutil -p -
```

The ad-hoc build listed `com.apple.security.get-task-allow => true` beside the app's own
resource-access entitlements. Under hardened runtime that entitlement re-enables task-port access,
so a terminal or password manager built this way is attachable by any process running as the same
user. Only a Developer ID re-sign drops it.

The grant is keyed to the code signature, and an ad-hoc cdhash changes on every rebuild, so each
redeploy can cost another round of prompts.
