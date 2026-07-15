# Tauri v2: the webview can invoke commands during `setup()` (init race)

In Tauri v2 the webview is coupled to the app lifecycle, not started by you after the backend is "ready." A window declared in `tauri.conf.json` (even `visible: false`) is created early, and its webview loads `index.html` and can `invoke()` commands **while `setup()` is still running** — and those command handlers run on the async-runtime thread pool, concurrently with `setup()` on the main thread.

So a command that reads state managed *inside* `setup()` can run **before** `app.manage(State)` executes, and get whatever the command falls back to. The classic footgun:

```rust
#[tauri::command]
pub fn get_config(app: AppHandle) -> Config {
    app.try_state::<ConfigState>()
        .map(|s| s.snapshot())
        .unwrap_or_default()   // <-- returns Config::default() if called before manage()
}
```

The frontend does `config = await getConfig()` at mount, gets `Config::default()`, and **latches onto it** — a wrong value silently disabling a feature for the whole session (in the dashboard: `auto_resize: None` → the resize measure early-returns → the window is frozen at its launch height). Intermittent (~1/3 of launches), timing-dependent, and maddening to debug because it looks like a frontend bug.

There is **no clean "backend ready → then boot frontend" barrier** — the webview boots itself. So handle it explicitly.

> **CORRECTION (2026-07-11, verified): the "manage-first-in-setup + frontend re-read" pattern below is INSUFFICIENT — it left ~24% of relaunches still broken. The definitive fix is to manage frontend-read state BEFORE any webview exists. The clean way: split `Builder::build(ctx)?` (returns the App with NO windows) from `App::run()` (creates them), and `app.manage(...)` everything the frontend reads in the gap between — `app.path().app_data_dir()` is live there (Tauri's own resolver, no `dirs` dep), and no webview exists yet. Manage the `FrontendLogger`/tracing subscriber there too — a `State<FrontendLogger>` command that races doesn't just log wrong, it drops the log entirely (rejected invoke), hiding the very race you're debugging. (An alternative is to resolve the path yourself pre-Builder via `dirs::data_dir().join(&ctx.config().identifier)` and `.manage()` on the Builder — works, but adds a `dirs` dep pinned to Tauri's major; prefer the build()/run() split.) See `tauri-ipc-startup-race.md` for the full pattern and the 0-vs-~24% measurement. Keep the sections below only as the fallback for a value that genuinely cannot move before run().**

## Fix pattern (no poll)

1. **Manage frontend-read state FIRST in `setup()`.** Move `app.manage(ConfigState)` (and any other store the mount reads, e.g. a `PromptHistoryStore` backing a `get_setup_state`) above the other stores and window setup. This shrinks the race window toward zero — the frontend's mount fetch happens tens of ms after webview start, after setup's first lines.

2. **Frontend re-reads authoritatively once, after the backend is demonstrably up.** At the END of `onMount` — after `getSessions`/`getUsageLimits`/etc. have already round-tripped (proving the backend answers commands) — do one `config = await getConfig()`. A single sequenced read, not a retry loop. Place it *before* any reveal `finally` block: a pre-show `requestAnimationFrame` await can stall while the window is hidden and skip anything after it.

3. **Cheap event backstops.** Have `show_window` (called by the frontend after it registers its `config_updated` / `setup_state` listeners) re-emit the authoritative state — the frontend *pulls* the trigger, so the listener is registered when the push arrives. If there's a **safety-net reveal timer** (a backend `spawn` that shows the window when the frontend's own `show_window` is slow/broken), it must ALSO re-push config/setup — else the reveal path bypasses the correction and the stale value sticks.

## Fully-deterministic alternative (usually overkill)

A readiness barrier: `setup()` fires a `tokio::sync::Notify` (or sets an `AtomicBool`) at its very end, and a `wait_until_ready` command awaits it; the frontend `await waitUntilReady()` before its first read. Correct but more machinery, and `Notify` has its own footgun — `notify_waiters()` only wakes tasks *already* parked, so firing before the waiter exists loses the wakeup (use `notify_one`'s stored permit or the check-flag-then-`notified()` pattern). Worth it only when the race is wide/high-stakes and there's no cheap self-healing backstop; the barrier's failure mode (hang forever) is worse than a benign stale read.

## Debugging notes

- **Multi-window log interleaving:** if several windows share one root component (routing by `getWindowLabel()`), they all run the same mount/measure code and log to the same file. Filter logs to the window you care about (e.g. by a mode flag) before concluding "the main window is failing" — the noise is often secondary windows correctly early-returning.
- Validate with **ground truth** (actual window rect via Win32 `GetWindowRect`), not just "did a command fire" — an absent action can mean "already correct," not "broken."
