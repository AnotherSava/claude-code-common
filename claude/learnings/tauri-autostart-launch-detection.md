# Detecting an autostart (login) launch in Tauri

`tauri-plugin-autostart`'s `init()` takes an optional args list that gets appended to the OS launch command (registry entry on Windows, LaunchAgent on macOS):

```rust
tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec!["--autostarted"]))
```

At startup, `std::env::args().any(|a| a == "--autostarted")` tells you the process was launched by the OS at login vs. started manually. This is the gate for a **"start minimized to tray"** mode: enable autostart but, when the marker is present *and* a persisted `start_minimized` flag is set, keep the main window hidden (only the tray icon appears); a manual launch always reveals it.

To actually stay hidden you must suppress *every* automatic reveal path your app has (e.g. a frontend mount-time `show_window` IPC call and any safety-net "reveal after N ms" timer) — gate them on a managed `AtomicBool`. The tray "Show/Hide" entry should call `window.show()` directly so it's unaffected.

**Migration gotcha:** the args list is baked into the launch command only when `enable()` runs. Users who enabled autostart under an older build (no marker) keep a marker-less entry until they re-toggle the mode — so treat "marker absent" as "show window" (the safe default), and re-enabling on mode change refreshes the entry.

Derive the three-state tray menu (Off / Open window / Open to tray) from `(autolaunch.is_enabled(), start_minimized)` rather than persisting the enabled bit separately — the OS owns enabled-ness; config only stores the extra `start_minimized` bit.
