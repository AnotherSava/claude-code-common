# Tauri v2: webview can call commands before setup() finishes

Windows declared in `tauri.conf.json` are created early — their webview loads and can `invoke()` commands **concurrently with**, and sometimes **before**, the `setup()` hook finishes. Any command that reads state managed *inside* `setup()` can therefore run before that state exists.

## The trap

State managed on the **Builder** (before `.run()`) is available before any command can run:

```rust
tauri::Builder::default()
    .manage(AppState::new())   // always available
```

State managed **inside `setup()`** races the webview:

```rust
.setup(|app| {
    let path = app.path().app_data_dir()?.join("config.json"); // needs the handle
    let cfg = ConfigState::new(path);
    app.manage(cfg);            // ← a webview get_config can beat this line
    Ok(())
})
```

A command that papers over the missing state with a default returns a misleading value during the race:

```rust
#[tauri::command]
fn get_config(app: AppHandle) -> Config {
    app.try_state::<ConfigState>().map(|s| s.snapshot()).unwrap_or_default() // default during race
}
```

The frontend caches that default at mount and **never recovers** (no event corrects it) — e.g. a config flag reads as its default forever, silently disabling a feature (a window that won't auto-resize, a toggle stuck off, etc.).

Symptom & confirmation:
- The backend log shows the *real* state value, but the frontend holds the default.
- It's **intermittent** across launches — depends on whether the webview wins the race against `setup()`.
- Confirm by logging `try_state::<T>().is_some()` inside the command: it's `false` on the racing call. (Tracing emitted before the subscriber is installed early in `setup()` may itself be dropped, so the racing call can have *no* log line at all — another tell.)

## Fixes (in order of preference)

1. **Manage the state on the Builder**, before any window exists — eliminates the race outright. Only works if the state can be constructed without the runtime app handle. Path-derived state (config, stores under `app_data_dir`) usually *can't*, which is exactly why it ends up in `setup()` and races.

2. **Push the authoritative value once the app is ready.** The frontend registers its update-event listeners *before* it calls the `show_window` command (it shows the window last, after wiring up `onMount`). So emitting the real value from `show_window` reliably reaches a registered listener and corrects any raced default:

   ```rust
   #[tauri::command]
   fn show_window(window: WebviewWindow) -> Result<(), String> {
       window.show().map_err(|e| e.to_string())?;
       window.set_focus().map_err(|e| e.to_string())?;
       emit_config_updated(window.app_handle()); // listener already registered frontend-side
       Ok(())
   }
   ```

3. Do **not** try to dodge the race by creating the window programmatically (to defer it past `setup()`): on Windows, dynamic `WebviewWindowBuilder` windows have broken IPC — see `tauri-windows-native`.

Anti-pattern: emitting the corrective event at the **end of `setup()`**. That typically fires before the webview's JS has even loaded and registered listeners, so it's missed. The push must be triggered by something the frontend does *after* it's listening (like `show_window`).
