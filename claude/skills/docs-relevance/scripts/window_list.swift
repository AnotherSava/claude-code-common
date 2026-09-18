// Dump every on-screen top-level window as JSON, for a capture script to match on.
//
// This exists because `screencapture` can photograph a window only by its
// CGWindowID, and nothing in the shell hands one out: `osascript` reports
// Accessibility window references, which are a different namespace, and there is
// no `screencapture --list`. CGWindowListCopyWindowInfo is the only public
// source of the id.
//
// Run interpreted (`swift window_list.swift`) rather than compiled: it costs
// about a second, it is called two or three times per capture, and a checked-in
// binary would be an unsigned architecture-specific artifact. Xcode Command Line
// Tools are already present on any Mac set up to build a native app, so `swift`
// adds no dependency a capture did not already have.
//
// Window TITLES are readable here only because the calling terminal holds the
// Screen Recording permission; without it CoreGraphics returns the window list
// with every name blanked. That is the same grant `screencapture` needs to
// photograph anything, so a run that can capture can always match on title —
// there is no state where this degrades silently and the capture still works.
//
// `layer` is reported and never filtered here. It is the window's level, and the
// widget runs always-on-top, so it does not necessarily sit at the 0 an ordinary
// window does — a filter in this file would be a guess about one window baked
// into the tool every script shares. The caller knows which window it wants and
// matches on owner and title; `layer` is there so a tie can be broken by it if
// one ever needs to be.

import CoreGraphics
import Foundation

let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let raw = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    FileHandle.standardError.write("window_list: CGWindowListCopyWindowInfo returned nothing\n".data(using: .utf8)!)
    exit(1)
}

var out: [[String: Any]] = []
for w in raw {
    let bounds = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
    out.append([
        "id": w[kCGWindowNumber as String] as? Int ?? 0,
        "owner": w[kCGWindowOwnerName as String] as? String ?? "",
        "pid": w[kCGWindowOwnerPID as String] as? Int ?? 0,
        "title": w[kCGWindowName as String] as? String ?? "",
        "layer": w[kCGWindowLayer as String] as? Int ?? 0,
        "x": bounds["X"] as? Double ?? 0,
        "y": bounds["Y"] as? Double ?? 0,
        "w": bounds["Width"] as? Double ?? 0,
        "h": bounds["Height"] as? Double ?? 0,
    ])
}

FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: out))
