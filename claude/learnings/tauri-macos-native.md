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

## Window geometry timing pitfalls (mid-launch and post-resize)

Three macOS-specific lag/aliasing traps that hit any Tauri code reading
window dimensions or scale around `setup()` or right after `set_size()`.

### `window.outer_size()` lags `set_size()` by several frames

On macOS, reading `outer_size()` immediately after `set_size(LogicalSize)`
returns the *old* size. The new size only appears once the NSWindow has
re-rendered. Code that does `set_size(...); let actual = outer_size()?;`
and clamps against `actual` is silently computing the clamp against the
pre-resize geometry — the window grows past the work-area edge and only
your clamp pass moves it back, creating a visible off-screen flicker.

Fix: don't read it. Compute the new size from `requested_logical × scale`
yourself and clamp against that.

### `window.scale_factor()` is unreliable before the window is realized

At `setup()` time, `WebviewWindow::scale_factor()` reads
`NSWindow.backingScaleFactor`, which on a hidden/not-yet-screened window
can lag the actual display's value (returns 1.0 on retina, etc.). The
positioning math then halves and the window lands off-screen.

Fix: use `Monitor::scale_factor()` (returned by `primary_monitor()` /
`current_monitor()`). Tauri bakes the value into the `Monitor` struct
when it queries the display, so it's not subject to NSWindow timing.

### `parent: "main"` in tauri.conf.json cascades visibility on macOS

On macOS, `parent: "main"` maps to NSWindow `addChildWindow:ordered:`,
which cascades show/hide from parent to child. A hidden About window
*will* auto-appear the moment the main window is first revealed — frontend
mode-gating (e.g. `aboutMode` in App.svelte's `finally { showWindow() }`)
is too late, because the OS shows the child before the JS ever runs in it.

Win32 owned windows do NOT cascade — the same `parent: "main"` works fine
on Windows. To keep an About / preferences modal hidden until the user
opens it, omit `parent` entirely on macOS and use `alwaysOnTop` for the
float-on-top feel.

### Move before resize to avoid off-screen intermediate frames

When a resize would push the window past the work-area edge and your
clamp logic moves it back, the OS sees two events: (1) `set_size` →
window briefly straddles the edge; (2) `set_position` → window jumps
back. The user sees a flicker.

Order them as `set_position; set_size` and the intermediate state is
always "new position, old size" — fully on-screen.

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
- **`is_enabled()` is `self.get_file().exists()`** in LaunchAgent mode
  (`auto-launch/src/macos.rs`) — pure plist-file existence, nothing else.

### The OS entry is a bad single source of truth

Because `is_enabled()` only asks whether the plist exists, the plist can be
deleted by something that is not the user — a Homebrew cask's
`uninstall launchctl:` stanza does exactly that, on every uninstall *and*
every upgrade. An app that enables autostart only on first run then has no
way to tell "the user opted out" from "a packager removed it", and autostart
silently stays off forever.

The fix is to split intent from mechanism: persist a `wanted` flag in your own
config, keep the OS entry as the mechanism, and reconcile at startup.

```rust
match config.autostart {          // Option<bool>; None = not yet recorded
    None => { /* seed from is_enabled() so existing opt-outs survive */ }
    Some(true) if !enabled_now => { let _ = app.autolaunch().enable(); }
    _ => {}
}
```

Make the repair **one-directional** — re-create a missing entry, never remove
a present one. Turning a login item off in System Settings → Login Items marks
it disabled in Background Task Management but leaves the plist on disk, so
`is_enabled()` still reports true; a symmetric "config says false, so disable"
branch would be unable to distinguish that from an opt-out and would fight the
OS-level choice. Whatever writes the setting in your UI must write both halves,
or the next launch will undo an "off" chosen there.

## Control+click on a tray icon must open the menu (secondary-click convention)

On macOS, Control+click is the system-wide **secondary click** — Apple defines
it as the exact equivalent of a right-click / two-finger click, and a menu bar
item is expected to open its menu on it. But if you bind left-click to a custom
action (toggle a widget, pause/resume) via `show_menu_on_left_click(false)`,
Control+click silently does the *left* action instead of opening the menu.

Root cause, confirmed down to the crate source: AppKit delivers Control+click as
a **`leftMouseDown` with the Control modifier flag set** — it does *not*
synthesize a `rightMouseDown`. The `tray-icon` crate's macOS handler reports it
as `MouseButton::Left` and **drops the modifier** — `TrayIconEvent::Click`
carries no modifier field (still true on the newest 0.24.x and `dev`; upstream
issue [#112](https://github.com/tauri-apps/tray-icon/issues/112) has been open
with no PR since 2024). Tauri's wrapper exposes no modifier either. So you can't
learn it from the event — you must query the live modifier state yourself.

**Step 1 — recover the modifier** via CoreGraphics C FFI (same style as
`idle.rs`, avoids an Objective-C runtime dep). `kCGEventFlagMaskControl` is
`1 << 18`, identical to `NSEventModifierFlagControl`:

    #[cfg(target_os = "macos")]
    fn control_key_held() -> bool {
        #[link(name = "CoreGraphics", kind = "framework")]
        extern "C" {
            fn CGEventSourceFlagsState(state_id: i32) -> u64; // 0 = combined session state
        }
        unsafe { CGEventSourceFlagsState(0) } & (1 << 18) != 0
    }

(Objective-C alternative: `msg_send![class!(NSEvent), modifierFlags]` via
`objc2` — equivalent, but adds a direct dep.)

**Step 2 — open the menu. Strongly prefer the native `show_menu()`** so
Control+click renders the *identical* menu to right-click. `show_menu()` landed
in **tray-icon 0.22.0** (PR #294) and drives the same `performClick` path as a
right-click, so the status item highlights and the menu anchors flush under the
icon. Tauri's tray wrapper doesn't re-export it, but you can reach it through the
public `with_inner_tray_icon` — and the `on_tray_icon_event` closure's first
param already *is* the Tauri `TrayIcon` handle:

    // tauri >= 2.11 pins tray-icon 0.24 (has show_menu); otherwise require tray-icon >= 0.22
    #[cfg(target_os = "macos")]
    if control_key_held() {
        let _ = tray.with_inner_tray_icon(|inner| inner.show_menu());
        return;
    }
    toggle_window(tray.app_handle()); // normal left-click

**Fallback for tray-icon < 0.22 (no `show_menu`):** pop the menu yourself with
Tauri's public `ContextMenu::popup` (`use tauri::menu::ContextMenu`; keep a
`menu.clone()`, since the builder only borrows it), branching in the `Left`/`Up`
arm on `control_key_held()`. **Caveat — this does NOT look like the native
menu:** `popup` renders a *floating context menu* at the cursor with **no
status-item highlight**, not anchored to the icon — visibly different from the
right-click menu. That cosmetic mismatch is the reason to bump tray-icon and use
`show_menu` instead. If you must use `popup`: it takes `position: None`, so muda
pops at `NSEvent::mouseLocation()` in **screen** coords (right under the icon); do
**not** use `popup_at`, whose position is **window-relative** (lands over the
widget, not the icon).

Either way, don't add an explicit `Right`/`Up` arm — right-click and two-finger
click already pop the menu **natively** (the crate calls `performClick` on
`rightMouseDown`, regardless of `show_menu_on_left_click`); a manual popup there
double-pops. Only the Control+Left path needs handling. Gate it all to macOS — on
Windows the menu convention is right-click and Ctrl+click keeps the left action.

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

## Signing & distribution without an Apple Developer ID

Two distinct things to know.

**`bundle.macOS.signingIdentity: "-"` in `tauri.conf.json` is not just cosmetic.**
Without it, Tauri emits a *linker-signed* bundle (the executable is signed by `ld` itself at build time but the bundle has no proper signature with resource sealing). When that bundle is wrapped into a DMG and extracted later, `codesign --verify` returns `code has no resources but signature indicates they must be present`, and Gatekeeper rejects it. With `"-"`, Tauri's bundler runs a proper `codesign --force --deep --sign -` over the whole bundle, sealing all resources. `codesign -dv` then reports `Sealed Resources version=2 rules=13 files=1` and verifies clean. The cost of leaving the flag out is silently shipping bundles that fail to launch on user machines.

**On modern macOS, a quarantined ad-hoc-signed app shows "damaged and can't be opened" — *not* "unidentified developer".**
The familiar right-click → Open trick **does not bypass it** for ad-hoc apps anymore (it still works for some unsigned cases, but not the ad-hoc + quarantine combination Gatekeeper labels as "damaged"). The two workarounds that do work for end users:

- **System Settings → Privacy & Security**, scroll to the blocked-app notice, click **Open Anyway**. No terminal needed.
- `xattr -dr com.apple.quarantine "/Applications/<App Name>.app"` to strip the quarantine flag. Prefer this over `xattr -cr`, which clears *every* extended attribute — including `com.apple.provenance`, which macOS sets on first launch and which is not yours to discard. The strip must recurse (`-r`): the attribute is written onto files inside the bundle, not just the top level.

`spctl -a -vv` will always say `rejected` for ad-hoc apps — that's expected, it only means "not Apple-notarized", and is not what triggers the "damaged" error. The "damaged" error is specifically a quarantine + non-Developer-ID combination.

**Do not run `spctl --assess` from a subagent, script, or any unattended context on macOS 26.** It raises a LocalAuthentication Touch ID / password dialog and *blocks* until a human answers — the unified log shows `coreautha … LADFRController _iconFromPath: /usr/sbin/spctl`, and because the dialog is named after the requesting binary it reads to the user as an offer to install something called "spctl". For unattended signature inspection use `codesign -dvvv`, `codesign -d --entitlements -`, and `xattr -l` / `xattr -r -l`, none of which prompt.

For shipping one of these bundles through Homebrew, see `homebrew-cask-unsigned-macos-app.md`.

Locally-built bundles (e.g. via a `deploy` script copying the .app to `/Applications/`) don't get the quarantine flag — it's only applied by browsers/email clients/downloaders when files cross the network. So your own dev workflow stays clean; only end-user downloads hit this.

## `minimumSystemVersion` defaults to 10.13 and will under-declare your app

`bundle.macOS.minimumSystemVersion` defaults to `"10.13"` (High Sierra), so an app that never sets it ships an `Info.plist` claiming support for macOS versions it cannot possibly run on — Tauri v2 itself needs 10.15+, and an arm64-only build needs Big Sur at minimum since no earlier macOS runs on Apple Silicon. Nothing breaks loudly; the bundle just lies, and the lie surfaces when a packaging system (a Homebrew cask's `depends_on macos:`, an installer's requirement check) is derived from it or has to contradict it.

Set it explicitly to whatever the docs actually promise:

```json
"macOS": {
  "signingIdentity": "-",
  "minimumSystemVersion": "11.0"
}
```

`MacConfig` is declared `#[serde(rename_all = "camelCase", deny_unknown_fields)]`, which is a useful property: a misspelled key under `bundle.macOS` is a hard build failure rather than a silently ignored setting. So `npx tauri info` parsing cleanly is real evidence the key name is right, not just that the JSON is well-formed.

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
