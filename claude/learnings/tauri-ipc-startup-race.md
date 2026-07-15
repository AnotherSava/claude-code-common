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

1. **Manage frontend-read state before any webview exists — this eliminates the race outright and is the ONLY reliable fix.** The event-push backstops (#2) are *insufficient* on their own: on the dashboard, fixing the config race with `show_window` re-pushes + a frontend re-read still left **~24% of relaunches** in the bad state. Managing before the webview is a structural guarantee (there is no instant where the webview exists but the state is unmanaged), not a probabilistic shrink.

   **The clean way for path-derived state: split `build()` / `run()`.** `Builder::build(ctx)?` returns the `App` *without* creating any window; config-defined webviews are created only by `App::run()` (at `RunEvent::Ready`). But `app.path()` is live right after `build()`. So there is a gap — after `build()`, before `run()` — where Tauri's own resolver works and no webview exists yet. Manage everything the frontend reads there:

   ```rust
   let app = tauri::Builder::default()
       .manage(AppState::new())            // handle-independent state stays on the Builder
       .invoke_handler(...)
       .setup(|app| {                      // runs at Ready, AFTER windows exist:
           let cfg = app.state::<ConfigState>().snapshot(); // already managed below
           /* window / tray / service wiring only */ Ok(())
       })
       .build(tauri::generate_context!())
       .expect("build");
   let dir = app.path().app_data_dir().expect("app data dir"); // Tauri's OWN resolver
   app.manage(ConfigState::new(dir.join("config.json")));      // before run() → before any webview
   app.manage(frontend_logger);                                // manage the logger here too (see below)
   app.run(|_, _| {});
   ```

   This is race-free by construction, uses Tauri's own `app_data_dir()` (no `dirs` dep, nothing to keep in lockstep), and keeps `?` error handling. A Tauri maintainer endorsed this shape (tauri-apps discussion #8719). `.setup()` still runs — but only for window/tray/service wiring that genuinely needs Ready — and reads config from the now-managed state. Manage the **logger / tracing subscriber here too** (see the next section for why a racing logger command is uniquely nasty). Having eliminated the race, DELETE the #2 backstops.

   *Alternative (also valid, more brittle): resolve the path yourself before the Builder* via `dirs::data_dir()?.join(&ctx.config().identifier)` — byte-identical to `app_data_dir()` (`src/path/desktop.rs`) — and `.manage()` on the Builder. It works and needs no `build()`/`run()` split, but adds a direct `dirs` dep you must pin to Tauri's `dirs` MAJOR (a future Tauri on `dirs 7` could otherwise resolve a *different* dir), so it wants a version guard. Prefer the `build()`/`run()` split, which sidesteps all of that.

2. **(Fallback only, if some state genuinely can't move pre-build.) Push the authoritative value once the app is ready.** The frontend registers its update-event listeners *before* it calls `show_window` (it shows the window last, after wiring `onMount`), so emitting from `show_window` reaches a registered listener. Treat this as a backstop for one hard-to-move value, never as the primary fix — it left ~24% still-broken above.

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

## A `State<T>` command param DROPS the command's work when `T` is unmanaged (not just returns a default)

The `unwrap_or_default()` trap above is the *visible* failure. The nastier one: a command that takes the state as a `State<T>` **parameter** doesn't run at all when `T` is unmanaged — Tauri can't resolve the arg, so the invoke rejects and the handler body never executes:

```rust
#[tauri::command]
fn frontend_log(level: String, msg: String, logger: State<FrontendLogger>) { logger.log(...) }
// unmanaged → invoke rejects → nothing logged. Frontend does frontendLog(...).catch(()=>{}) → silent.
```

Consequences that cost real debugging time on the dashboard:
- **Early frontend logs vanished.** Every mount-time diagnostic (the measure attempts, readiness retries, a "mount snapshot") fired *before* `FrontendLogger` was managed in `setup()`, so it errored and was swallowed by the frontend's fire-and-forget `.catch`. The bug that most needed logs to diagnose produced *none* — it read as an unexplained "silent bail" for months.
- **Empirically, the racing logger even correlated with the primary feature breaking** (the window never measured), so managing `FrontendLogger` pre-build didn't just restore logs — it dropped the stuck-window rate to **0/105 relaunches**.

Takeaway: manage the logger/tracing subscriber pre-build alongside your config state (same `dirs`-derived `app_data` trick). Otherwise the very tool you'd use to see the race is itself a casualty of it. To tell a *real* failure from a *dropped-log* one, check a signal that does NOT depend on the racing state — e.g. a **backend tracing** line for the same action (its subscriber, once also managed pre-build, is reliable), or the observable effect itself (window rect).
