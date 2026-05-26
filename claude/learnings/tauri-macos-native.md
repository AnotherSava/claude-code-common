# Tauri on macOS — native customization

Companion to `tauri-windows-native.md`. macOS-specific patterns for tray-style
or accessory Tauri apps, runtime native APIs, and platform behaviors that
aren't surfaced by `tauri.conf.json`.

## Accessory activation policy (no Dock icon, no app menu bar)

For a tray-only widget — the macOS analogue of Windows `skipTaskbar: true` —
call this in your Builder::setup():

    #[cfg(target_os = "macos")]
    app.set_activation_policy(tauri::ActivationPolicy::Accessory);

`Accessory` keeps the app off the Dock and out of Cmd-Tab; the global app
menu bar (Apple, File, Edit, …) also disappears because the app never
becomes "active". The window itself still renders normally and still gets
focus when clicked. This is a runtime equivalent of setting
`LSUIElement = true` in Info.plist.

## Killing the white flash on first window show

A frameless dark-themed window will flash white on first `show()` even when
`tauri.conf.json` has `backgroundColor: "#1c1c1e"`. The config-level field
isn't applied early enough on macOS, *and* it only addresses the NSWindow,
not the WKWebView's own CALayer backing or the document root. Three layered
fixes are needed; any one or two alone is insufficient.

**1. Set the NSWindow background at runtime, before any show:**

    use tauri::window::Color;
    let _ = window.set_background_color(Some(Color(0x1c, 0x1c, 0x1e, 0xff)));

This maps internally to `NSWindow.setBackgroundColor:` plus the WKWebView's
under-page color.

**2. Set the HTML document root to the same color (not transparent):**

    html, body {
      background: #1c1c1e;  /* not 'transparent' */
    }

The page's `.widget` div may cover the viewport in CSS, but if the WKWebView
takes a first-paint snapshot before that div has been laid out, the
document root color is what fills the frame. Make it match.

**3. Gate `show()` behind two animation frames so the compositor has time
to paint a dark frame:**

    await tick()  // flush Svelte updates
    await new Promise<void>(r =>
      requestAnimationFrame(() => requestAnimationFrame(() => r()))
    )
    await showWindow()  // calls Window::show() in Rust

`tick()` only flushes the framework's update queue. The browser still needs
its own frame to composite, and on macOS `show()` happens fast enough that
the OS reveals the window before the first composit lands. Two rAFs
(rAF-rAF, not rAF alone) is the standard "wait for next paint" idiom.

The window starts hidden (`visible: false` in tauri.conf.json) and the
frontend calls a `show_window` Tauri command at the end of mount; this is
also where the rAF gating goes. A 1500ms safety net in the Rust setup() is
fine to keep — it only fires if the frontend never calls show.

## Default window positioning: work_area() vs size()

`tauri::window::Monitor::size()` returns the **full screen** including the
Dock/menu bar (macOS) and the taskbar (Windows). Positioning a "bottom-right
of screen" widget with `screen.height - window.height - margin` will leave it
partially hidden under the Dock on macOS, and many projects compensate with a
hardcoded `taskbar_allowance` constant.

Tauri 2.x exposes `Monitor::work_area() -> &PhysicalRect<i32, u32>` — the
usable rect that the OS reports as free of Dock/menu bar/taskbar chrome. Use
it instead and drop the platform-specific allowance:

    let work = monitor.work_area();
    let x = work.position.x + work.size.width as i32 - size.width as i32 - margin_x;
    let y = work.position.y + work.size.height as i32 - size.height as i32 - margin_y;

`PhysicalRect` has `position: PhysicalPosition<i32>` and
`size: PhysicalSize<u32>`. This is cross-platform — works on Windows
(excludes taskbar) and Linux too. Always prefer `work_area()` over `size()`
for positioning logic unless you specifically want absolute screen
coordinates.

## acceptFirstMouse: clicks on inactive windows reach the webview

By default on macOS, clicking on an inactive (non-key) window only
activates it — AppKit consumes the click and it never reaches the
webview. For a multi-window app where the user expects a single click on
a background window to register (e.g. clicking a dashboard row to toggle
a popover that has focus), this manifests as needing TWO clicks: the
first activates, the second triggers.

Tauri exposes this as a per-window config flag in `tauri.conf.json`:

    "app": {
      "windows": [
        { "label": "main",    "acceptFirstMouse": true, ... },
        { "label": "history", "acceptFirstMouse": true, ... }
      ]
    }

Default is `false`. Maps to NSView's `acceptsFirstMouse(_:) -> true`.
macOS-only — no effect on Windows/Linux. Set on every window where you
want click-through-on-activation behavior.

## Cross-platform bundle.targets

`bundle.targets: ["nsis", "app", "dmg"]` works fine across platforms — Tauri
silently skips targets that don't apply to the current platform, so Windows
builds nsis, macOS builds app+dmg, no per-OS branching needed. `"all"` is the
even simpler form if you want every default for the current platform.

## tauri-plugin-autostart on macOS

With `MacosLauncher::LaunchAgent`, calling `app.autolaunch().enable()` writes:

    ~/Library/LaunchAgents/<productName>.plist

containing a Label = productName (with spaces, not reverse-DNS), the absolute
ProgramArguments path to the binary, and `RunAtLoad: true`. Caveats:

- Calling `enable()` from a `tauri dev` session writes the **debug** binary
  path, which silently breaks at next login if the target/ folder gets
  cleaned. Don't auto-enable on first run from dev builds — or always toggle
  off before exiting.
- `disable()` removes the plist; `enable()` then `disable()` is a clean
  round-trip.
- The auto-launch crate (which the plugin wraps) takes a `set_app_path`,
  not a bundle path — for a `.app` bundle, point it at
  `Contents/MacOS/<binary>`.

## Testing tray menus via AppleScript

NSStatusBar items are `menu bar item N of menu bar 2 of process "<binary>"`
(menu bar 1 is the global app menu). To list and click programmatically:

    osascript -e 'tell application "System Events" to tell process "myapp" \
      to get count of menu bars'  # 2 if the app has a tray

    osascript -e 'tell application "System Events" to tell process "myapp" \
      to click menu bar item 1 of menu bar 2'                    # opens menu

    osascript -e 'tell application "System Events" to tell process "myapp" \
      to click menu item "Open on system start" of menu 1 \
      of menu bar item 1 of menu bar 2'                          # clicks item

Process name in `process "X"` is the **binary name** (Cargo `[package].name`,
not productName). Requires Accessibility permission for whatever process is
running osascript (Terminal, Kitty, etc.) — toggleable in
System Settings → Privacy & Security → Accessibility.

## Reading the Keychain from an unsigned Tauri app

macOS Keychain entries carry an ACL ("partition list") of code-signed identities allowed to read without prompting. Items created by Claude Code allow Apple-signed binaries (including `/usr/bin/security`) but not our unsigned dev build — reads from a Rust crate like `keyring` trigger a SecurityAgent prompt every time.

For unsigned builds the prompt is also **not durable** across rebuilds — macOS keys "Always Allow" by the binary's code-signing identity, which for unsigned bundles is the binary hash. Every `tauri build` produces a fresh hash, so the user re-approves on every deploy.

**Workaround until you have a Developer ID:** shell out to `/usr/bin/security` instead of using a Rust Keychain crate. The CLI is Apple-signed and on the partition list of Claude Code's entries (and most others), so reads silently succeed.

    let out = Command::new("/usr/bin/security")
        .args(["find-generic-password", "-s", "Claude Code-credentials",
               "-a", &username, "-w"])
        .output()?;
    let json = String::from_utf8(out.stdout)?.trim().to_string();

Write with `add-generic-password ... -U` (update-or-create). One caveat: `security add` takes the password as an argv, so it's briefly visible via `ps` — fine for low-stakes secrets and infrequent writes (e.g. OAuth token rotation every 30 days), not fine for high-value secrets or hot paths.

When you do get a Developer ID, switching to a Rust crate becomes viable — the signed identity stays stable across rebuilds, and "Always Allow" sticks.

## TCC permissions you'll hit

- **Screen Recording** (System Settings → Privacy & Security): needed for
  `screencapture` from any process, including Terminal. Failure mode is
  `could not create image from display` (exit 1, no other diagnostic).
- **Accessibility**: needed for `osascript` doing System Events / UI element
  scripting. Failure is `osascript is not allowed assistive access. (-1719)`.

Both prompts only fire on first attempt; once granted, persist per-process.
