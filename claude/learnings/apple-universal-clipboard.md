# Apple Universal Clipboard: relaying it, and the one-way failure

iOS lets no app read or write the clipboard in the background, so a cross-platform sync tool cannot have a real iOS client, and Apple's own Universal Clipboard is what reaches an iPhone's clipboard without a tap. The workable design is to let a Mac relay. A sync tool keeps a Windows or Linux machine in step with the Mac's clipboard, and Universal Clipboard carries it between the Mac and the iPhone. Measured 2026-11-13 with ClipCascade between a Windows desktop and a Mac on macOS 27.0.1: once the one-way failure described here was fixed, copies travelled both ways across all three devices.

## Why the Mac can relay

Both directions rest on documented behaviour:

- **Programmatic writes are forwarded.** Universal Clipboard advertises whatever lands on the Mac's general pasteboard, whoever wrote it. A writer keeps an item local only by opting out with `NSPasteboard.prepareForNewContents(with: .currentHostOnly)`. A sync tool that writes through `pbcopy`, `pyperclip` or a plain `setString:forType:` is forwarded to the iPhone.
- **Background readers see iPhone copies.** An item that arrives from another device sits on the Mac pasteboard carrying the type `com.apple.is-remote-clipboard`, and `changeCount` increments, so a poller notices it without anyone pasting. Clipboard managers document this from the other side: Maccy's FAQ tells users to add that type to its ignore list to keep iPhone copies out of history.

Before trusting a sync tool as the relay, check its macOS reader does not skip items with that type. Some do on purpose, to avoid echo loops. ClipCascade v3.5.1 does not filter by type at all.

macOS 15.4 previewed a "Paste from Other Apps" permission that alerts when an app reads the pasteboard without a paste gesture. If a later macOS enforces it, the sync tool needs that permission under Privacy & Security, granted once.

## iPhone → Mac broken while Mac → iPhone works

This one-way failure is widely reported on macOS and iOS 26 and 27, and it breaks the relay in the iPhone → anywhere direction. Separate the hops before blaming the sync tool: copy on the iPhone and press Cmd+V on the Mac, with the sync tool out of the picture.

The fix that worked on 2026-11-13 is a user-reported workaround from Apple Discussions, not an Apple fix:

```bash
defaults read com.apple.coreservices.useractivityd ClipboardSharingEnabled   # the key was absent on the Mac measured here
defaults write com.apple.coreservices.useractivityd ClipboardSharingEnabled -bool true
killall useractivityd                                                        # relaunches by itself
```

Then on the iPhone, turn Handoff off and on in Settings › General › AirPlay & Continuity, restart the phone, and copy once Mac → iPhone before testing iPhone → Mac with fresh text. One report in the thread needed that Mac → iPhone copy before the other direction woke up. All of this was done in one go, so which step was needed is not known. To undo the change, run `defaults delete` on the same key.

The `com.apple.coreservices.useractivityd` domain also holds `kRemotePasteboardBlobName`, the path of a file under the user's Group Containers. While iPhone → Mac was broken that file had not changed for a week. Its modification time then moved to within a minute of the first iPhone → Mac copy the user reported working, and its size from 6 bytes to 170. That is one observation, and it makes the file's mtime a usable sign of when the Mac last received a copy from another device.
