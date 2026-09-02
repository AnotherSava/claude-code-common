// DocShot — capture a documentation screenshot of anything on screen.
//
// It exists as a separate app bundle for one reason: macOS TCC grants Screen
// Recording to a *binary*, and the agent that wants the screenshot is a bare
// executable named after its version (`~/.local/share/claude/versions/2.1.251`).
// Granting it there is both too broad — Screen Recording lets a process read the
// whole display at any time, for every session, forever — and too fragile, since
// the next update installs under a new name and the grant goes stale.
//
// This bundle's path and ad-hoc identity are stable, so the grant is made once
// and survives Claude Code updates. Rebuilding changes the ad-hoc signature and
// resets the grant, so build once and leave it alone.
//
// **Not everything worth documenting is a window.** A tray/menu-bar menu, a
// context menu, a tooltip and a popover are all separate CGWindows on a higher
// layer than 0, and a menu bar item is smaller than any sane size floor. So the
// layer filter is a default, not a rule, `--region` covers whatever has no
// window of its own, and `--delay` exists because those surfaces are transient:
// they have to be opened after the capture is already scheduled.
import Foundation
import CoreGraphics

struct Win {
    let id: CGWindowID, owner: String, title: String
    let x: Int, y: Int, w: Int, h: Int, layer: Int
}

func onScreenWindows() -> [Win] {
    let opts: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    let raw = (CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]]) ?? []
    return raw.compactMap { d in
        guard let id = d[kCGWindowNumber as String] as? CGWindowID,
              let b = d[kCGWindowBounds as String] as? [String: Any],
              let x = b["X"] as? Int, let y = b["Y"] as? Int,
              let w = b["Width"] as? Int, let h = b["Height"] as? Int else { return nil }
        return Win(id: id,
                   owner: d[kCGWindowOwnerName as String] as? String ?? "",
                   title: d[kCGWindowName as String] as? String ?? "",
                   x: x, y: y, w: w, h: h,
                   layer: d[kCGWindowLayer as String] as? Int ?? 0)
    }
}

func die(_ msg: String) -> Never {
    FileHandle.standardError.write(("docshot: " + msg + "\n").data(using: .utf8)!)
    exit(2)
}

let args = Array(CommandLine.arguments.dropFirst())
func opt(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}
func flag(_ name: String) -> Bool { args.contains(name) }

// Slept through FIRST, before anything is enumerated. A menu, popover or tooltip
// does not exist until it is opened and dies the moment focus moves, so the only
// order that can catch one is: schedule, let it be opened, then look.
if let d = opt("--delay"), let secs = Double(d) { Thread.sleep(forTimeInterval: secs) }

// `--out` is honoured in list mode too: TCC may insist this helper be launched
// through LaunchServices (`open -a`) to be the responsible process, and a process
// launched that way has nowhere to print — its stdout is not the caller's. A file
// is the one channel that survives either invocation style.
func emit(_ text: String) {
    if let p = opt("--out") { try? text.write(toFile: p, atomically: true, encoding: .utf8) }
    else { print(text) }
}

/// Whether Screen Recording is actually granted.
///
/// Without it, ids, owners and bounds still populate while every `title` comes
/// back empty — a denial that otherwise reads exactly like "the thing isn't on
/// screen". So an empty-title sweep is the probe, but it has to be narrowed
/// twice or it reports a false pass: **`Window Server` surfaces are readable
/// ungated** (its layer-24 "Menubar" always reports a title), and so is any
/// window this process owns itself. Only a *foreign, ordinary* window's title is
/// gated, so only that answers the question.
func granted(_ rows: [Win]) -> Bool {
    rows.contains { $0.layer == 0 && $0.owner != "Window Server" && !$0.title.isEmpty }
}

if flag("--list") {
    // No layer filter and a low size floor: the whole point of listing is to find
    // the menu or the status item that the capture defaults would hide.
    let rows = onScreenWindows().filter { $0.w >= 8 && $0.h >= 8 }
    let out = rows.map { ["id": Int($0.id), "owner": $0.owner, "title": $0.title, "layer": $0.layer,
                          "x": $0.x, "y": $0.y, "width": $0.w, "height": $0.h] as [String: Any] }
    let data = try! JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys])
    emit(String(data: data, encoding: .utf8)!)
    exit(granted(rows) ? 0 : 3)
}

if flag("--check") {
    let ok = granted(onScreenWindows())
    emit(ok ? "granted" : "denied")
    exit(ok ? 0 : 3)
}

guard let capturePath = opt("--out") else { die("need --out <path>  (or --list)") }

func run(_ extraArgs: [String], _ what: String) -> Never {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    // -o drops the window drop-shadow, -x silences the shutter.
    p.arguments = extraArgs + ["-o", "-x", capturePath]
    try! p.run()
    p.waitUntilExit()
    if p.terminationStatus != 0 { die("screencapture failed (\(p.terminationStatus)) — is Screen Recording granted to DocShot?") }
    guard FileManager.default.fileExists(atPath: capturePath) else { die("screencapture wrote nothing") }
    print("captured \(what) -> \(capturePath)")
    exit(0)
}

// A rectangle, for anything with no window of its own to name — a menu bar item,
// a region spanning two windows, one panel of a larger UI.
if let r = opt("--region") {
    let n = r.split(separator: ",").compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }
    guard n.count == 4 else { die("--region wants x,y,w,h") }
    run(["-R\(n[0]),\(n[1]),\(n[2]),\(n[3])"], "region \(r)")
}

if let idStr = opt("--id"), let id = UInt32(idStr) { run(["-l\(id)"], "window id \(id)") }

let owner = opt("--owner"), title = opt("--title")
if owner == nil && title == nil { die("need --owner/--title, --id, or --region  (see --list)") }

// Layer 0 is the ordinary-window default because it is what a caller naming an
// app almost always means. `--layer N` reaches a menu (101 on macOS) or a status
// item; `--any-layer` gives up filtering entirely.
let wantLayer = opt("--layer").flatMap { Int($0) }
let matches = onScreenWindows().filter { win in
    (owner == nil || win.owner.localizedCaseInsensitiveContains(owner!))
        && (title == nil || win.title.localizedCaseInsensitiveContains(title!))
        && (flag("--any-layer") ? true : win.layer == (wantLayer ?? 0))
}
if matches.isEmpty {
    die("nothing on screen matches owner=\(owner ?? "*") title=\(title ?? "*") "
        + "layer=\(flag("--any-layer") ? "any" : String(wantLayer ?? 0)) — run --list to see what is there")
}
// Refuse rather than guess: two matches is the caller's ambiguity to resolve, and
// picking one silently is how the wrong picture ends up in the docs.
if matches.count > 1 {
    die("\(matches.count) match — narrow with --id: "
        + matches.map { "id=\($0.id) layer=\($0.layer) \($0.owner)/\($0.title)" }.joined(separator: " | "))
}
let win = matches[0]
run(["-l\(win.id)"], "\(win.owner)/\(win.title) layer \(win.layer) (\(win.w)x\(win.h))")
