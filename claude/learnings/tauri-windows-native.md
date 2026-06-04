# Tauri on Windows — native customization

Reference for tasks that go beyond what `tauri.conf.json` and the cross-platform Tauri API expose. Most of this is Win32 territory accessed via `WebviewWindow::hwnd()` and raw `extern "system"` declarations (no need for the `windows`/`windows-sys` crate for small surface areas).

## HWND identity

`WebviewWindow::hwnd()` returns the **parent native window's** HWND, not the child WebView control. Subclasses installed on this HWND see all non-client messages (resize border, title bar area, etc.) for the window frame. The WebView is a child HWND that handles its own client-area messages independently.

## Sizing: inner vs outer

For frameless windows (`decorations: false`) with `resizable: true`, Windows still keeps `WS_THICKFRAME`, which adds an invisible resize border (~5 px) around the visible area.

- `set_size(LogicalSize)` writes the **inner** (client) size.
- `outer_size()` returns the full window rect including that invisible border.
- Mixing the two creates accumulating drift: read outer, set size from outer, read outer again, the border has been double-counted.

**Always use `inner_size()` for size reads if you'll feed the result back into `set_size`.**

### Positioning relative to a target outer edge

When the goal is "after resize, the window's *outer right* edge sits at column X" (e.g. preserve a right-edge margin against the work area), the obvious order — `set_position` to a computed new_x using the requested inner width, then `set_size` — produces the wrong final edge because outer ≠ inner.

Empirical example (decorationless, `decorations: false`, DPR 1.5):
- Requested logical width 597.33 → expected physical 896.
- Observed `outer_size().width` after `set_size` = **918** physical (~22 px wider — the invisible WS_THICKFRAME resize border, ~11 px per side at this DPR).
- If position math used 896, the window hung 6 px past the work area; if it used 918, position was correct.

Working pattern:

```rust
// 1. Resize first; defer position adjust until we know the actual outer size.
window.set_size(LogicalSize::new(target_logical_w, current_logical_h))?;

// 2. Read what the window manager actually produced.
let pos = window.outer_position()?;
let outer = window.outer_size()?;

// 3. Compute target position using actual outer width.
let monitor = window.current_monitor()?.unwrap();
let work = monitor.work_area();
let allowed_right = work.position.x + work.size.width as i32 - RIGHT_MARGIN_PX;
let overflow = pos.x + outer.width as i32 - allowed_right;
if overflow > 0 {
    let new_x = (pos.x - overflow).max(work.position.x);
    window.set_position(PhysicalPosition::new(new_x, pos.y))?;
}
```

The brief frame where the window is sized but not yet repositioned (one tick) is fine in practice — no user-visible flash on Windows.

## Maximized window save/restore

Persisting a window's geometry on close and restoring it on open has two non-obvious maximize traps on Windows.

**1. A maximized window's outer rect is inflated by the frame.** `outer_position()`/`outer_size()` on a maximized window report it sitting ~8 px past each work-area edge (where the invisible resize border goes), so the size is roughly `work + 16` on each axis. Saving that rect and re-applying it to an *unmaximized* window produces a free-floating window larger than the work area — and it can grow on each maximize→save→restore cycle. Don't capture bounds while maximized:

```rust
let maximized = window.is_maximized().unwrap_or(false);
state.with_mut(|c| c.window_maximized = maximized);
if !maximized {
    // Only the unmaximized geometry is a valid restore-rect.
    let pos = window.outer_position()?;
    let size = window.outer_size().ok();
    state.with_mut(|c| c.window_position = Some(/* pos + size */));
}
```

Persist a **separate `maximized: bool`** alongside the position (not a field inside the bounds struct — the flag must survive even when no bounds were ever saved), and keep the last *unmaximized* bounds untouched while maximized.

**2. Closing-as-hide preserves the maximized state, so a naïve restore flashes.** Reusable windows are typically closed via `api.prevent_close()` + `window.hide()` — which keeps the window maximized while hidden. On reopen it's *already* maximized, so restore code that unconditionally runs `unmaximize() → set_position() → set_size(normal) → maximize()` forces the window down to normal size and back up: a visible flash. Only touch geometry when the actual state differs from the target:

```rust
let already_max = window.is_maximized().unwrap_or(false);
match (saved_bounds, want_maximized) {
    (Some(p), false)            => { window.unmaximize(); set_pos_size(p); }
    (Some(p), true) if !already_max => { set_pos_size(p); window.maximize(); } // bounds first => restore-rect
    (Some(_), true)             => {} // already maximized — leave it, no flash
    (None, _) if !already_max   => { /* default position */ window.maximize(); }
    (None, _)                   => {}
}
window.show()?;
```

Setting the unmaximized bounds *before* `maximize()` makes them the OS restore-rect, so a later un-maximize returns to the right size.

**3. `maximize()` then `show()` in the same tick can still flash.** When the window starts un-maximized (first open after an app restart), an immediate `maximize()` right before `show()` may paint one normal-size frame before maximizing. Pre-apply the maximized state to the still-hidden window **at startup** (well before its first show, so the event loop settles it) — then the first open reveals it already maximized:

```rust
// in setup(), window pre-created hidden in tauri.conf.json
if cfg.save_window_position && cfg.window_maximized {
    if let Some(w) = app.get_webview_window("history") {
        if let Some(p) = cfg.window_position { set_pos_size_on(&w, p); }
        let _ = w.maximize();
    }
}
```

## Auto-resize loops vs Windows minimum window height

Windows enforces a minimum height (~150 device px, varies by frame style) for resizable windows. `WebviewWindow::set_size` to anything smaller succeeds silently — no error — but the subsequent `inner_size()` returns the clamped value, not the requested one.

If the frontend has an auto-resize loop that compares "desired content height" against `window.innerHeight` and re-fires on mismatch, this clamp creates a feedback loop:

1. JS measures content as 87, sends `apply_auto_resize(87)`.
2. Rust calls `set_size(87)`. Windows clamps to ~150. Inner is now 150.
3. JS resize handler fires. Measures 87, sees `window.innerHeight = 150`, fires again.
4. Loop continues at ~1 fire per measurement debounce until something else changes.

The log signature is identical `desired_logical_height` across rapid calls with drifting `new_y` (Up-mode anchors compute fresh deltas each pass):

```
{"desired_logical_height":87.0,"new_height_phys":87,"new_y":2037}
{"desired_logical_height":87.0,"new_height_phys":87,"new_y":2106}
{"desired_logical_height":87.0,"new_height_phys":87,"new_y":2189}
```

### Correct dedup strategy

Two cases need different treatment:

1. **Content overflows the viewport** (`desired > window.innerHeight`) — always fire. This is the original bug class (content too tall, scrollbar appears). Dedup must never block it, including across DPI shifts and monitor moves where `lastSentHeight` may be stale relative to the current viewport.
2. **Content fits the viewport** — dedup against `lastSentHeight` (what we last requested), not the viewport. Even if the actual window is taller than `desired` because of an OS clamp, re-asking for the same size won't help and we already requested it once.

```ts
let lastSentHeight = -1

function measure() {
    const desired = headerEl.offsetHeight + contentH

    const overflowing = desired > window.innerHeight + 1
    if (!overflowing && Math.abs(desired - lastSentHeight) < 1) return

    lastSentHeight = desired
    invoke('apply_auto_resize', { height: desired })
}

// Pair with a `resize` listener so DPI/monitor changes also trigger a
// re-measure — the dedup above prevents recursion when our own resize
// settles the window.
window.addEventListener('resize', scheduleMeasure)
```

The naive single-comparison alternatives both fail:

- Dedup against `lastSentHeight` alone: silently drops drift fires when the window's real size diverged from what we requested (DPI shift, monitor move, external resize). Content overflows, no resize.
- Dedup against `window.innerHeight` alone: loops forever on OS clamp.

The two-comparison form handles both.

## Threading

`SetWindowSubclass` (and most class-modifying APIs like `SetClassLongPtrW`) require the **window-creating thread**. Calling them from a tokio worker (e.g. inside `tauri::async_runtime::spawn` after a `tokio::time::sleep`) silently fails with no error in the logs except the explicit return-value check.

Pattern for delayed install on the right thread:

```rust
let window = window.clone();
tauri::async_runtime::spawn(async move {
    tokio::time::sleep(Duration::from_millis(500)).await;
    let win = window.clone();
    let _ = window.run_on_main_thread(move || {
        do_native_setup(&win);
    });
});
```

`Manager::run_on_main_thread` is the bridge — schedules a closure on the UI thread and returns immediately.

## Tray menus

`tauri::menu::Submenu` implements `IsMenuItem`, so a built submenu drops directly into an existing `Menu::with_items` array — no need to migrate to `MenuBuilder`:

```rust
let sub = SubmenuBuilder::new(app, "Auto resize")
    .items(&[&item_a, &item_b, &item_c])
    .build()?;
let menu = Menu::with_items(app, &[&always_on_top, &sub, &quit])?;
```

Hold every `CheckMenuItem` handle in `app.manage(...)` state if you'll need to update its checked state from a click handler.

## Subclass dispatch order vs wry

`SetWindowSubclass` adds to a chain. The **most-recently-installed** subclass is called **first** for incoming messages, then forwards via `DefSubclassProc` to the next-most-recent, and so on down to the original `WindowProc`. Each level can rewrite the return value before bubbling back up.

Wry installs its own subclass during webview attachment, which can happen before or after a Tauri `setup` callback. Empirically:

- For messages in **non-drag-region areas** (bottom edge, left/right edges), wry stays out of the way and a value our subclass returns reaches the OS unchanged.
- For messages **near a `data-tauri-drag-region`** element (the top header in this app), wry's subclass re-asserts the original hit-test value (e.g. `HTTOP`) to keep its drag-region detection working — overriding our `HTCLIENT`.

Delaying our install via `run_on_main_thread` to land after wry sometimes works, sometimes doesn't (wry may install on its own delays/events). Don't rely on chain order alone for messages that touch the drag region.

## Disabling vertical resize on a frameless window

Goal: only left/right edges resize; top/bottom/corners do nothing. There's no `set_resizable_directions` API.

What works (defense in depth):

1. **`WM_NCHITTEST` → `HTCLIENT`** for `HTTOP`/`HTBOTTOM`/`HTTOPLEFT`/`HTTOPRIGHT`/`HTBOTTOMLEFT`/`HTBOTTOMRIGHT`. Reliable for the bottom edge and corners. Top edge gets re-asserted by wry near the drag region.
2. **`WM_NCLBUTTONDOWN` → consume (return 0)** for the same hit-test values (carried in `wParam`). This is the message that *starts* the resize drag — independent of who won the hit-test. Reliable for both top and bottom. The functional resize block.

What doesn't work for the top-edge cursor:

- `WM_SETCURSOR` interception. Wry sets the cursor via direct `SetCursor()` calls inside its mouse-move handlers, not through `WM_SETCURSOR`, so our handler never observes the resize-cursor case.
- Subclass install order shuffling. Even installing well after wry, the cursor still flashes ↕ on the top edge when wry's handler runs.

The cosmetic ↕ flash on the top edge is the practical limit of subclass-based interception. The functional resize is solidly blocked by `WM_NCLBUTTONDOWN`.

Minimal subclass surface (no `windows`/`windows-sys` dep needed):

```rust
#[link(name = "comctl32")]
extern "system" {
    fn SetWindowSubclass(hwnd: isize, callback: SubclassProc, id: usize, refdata: usize) -> i32;
    fn DefSubclassProc(hwnd: isize, msg: u32, wp: usize, lp: isize) -> isize;
}
```

`SUBCLASS_ID` is any `usize` unique to your subclass — pick a distinctive value (e.g. ASCII bytes packed) for debugger visibility.

## White flash during horizontal resize

When the window grows wider, the OS paints the newly-exposed area with the **window class's `hbrBackground`** brush before the WebView catches up and renders content into it. Default class brush is white → white flash against a dark theme.

`tauri.conf.json`'s `backgroundColor` only affects the WebView background, not the underlying class brush.

Fix: replace the class brush at startup. One-time, no per-message handler.

```rust
const COLORREF_DARK: u32 = 0x001E_1C1C; // RGB(0x1c, 0x1c, 0x1e) — BGR encoded
const GCLP_HBRBACKGROUND: i32 = -10;

#[link(name = "user32")]
extern "system" {
    fn SetClassLongPtrW(hwnd: isize, index: i32, value: isize) -> isize;
}
#[link(name = "gdi32")]
extern "system" {
    fn CreateSolidBrush(color: u32) -> isize;
}

unsafe {
    let brush = CreateSolidBrush(COLORREF_DARK);
    if brush != 0 {
        SetClassLongPtrW(hwnd, GCLP_HBRBACKGROUND, brush);
    }
}
```

Don't `DeleteObject` the previous brush returned by `SetClassLongPtrW` — it may be a system color value (e.g. `COLOR_WINDOW+1`) rather than a real GDI handle, and feeding that to `DeleteObject` is undefined.

`COLORREF` encoding is `0x00BBGGRR` (low byte red), so `#1c1c1e` → `0x001E_1C1C`.

## Multi-window pitfalls

Attempting to add a second always-on-top overlay window (for a tooltip that extends past the main widget) revealed several issues:

**Capability JSON with non-existent window labels**: adding `"tooltip"` to the capability's `windows` array before the window exists can break IPC routing for the main window — `data-tauri-drag-region` drag and `app.exit(0)` both stopped working. Pre-declaring the window in `tauri.conf.json` (so it exists at startup) or using a separate capability file avoids this.

**Dynamically-created overlay windows break main window drag**: creating a `transparent(true)` + `always_on_top(true)` window at runtime broke the main window's drag detection even after hiding the overlay. Root cause is likely focus migration during creation — `focused(false)` in the builder prevents initial focus but doesn't prevent the window from being focusable. The drag region's `start_dragging` IPC requires the window to be the foreground window.

**`app.exit(0)` silently no-ops from tray menu handlers**: observed after adding a second window. `std::process::exit(0)` bypasses Tauri's exit pipeline entirely and is reliable for tray widgets where there's no graceful work to flush.

**Native `title` tooltips already escape the window**: the browser's `title` attribute renders an OS-level tooltip (a separate native window managed by the webview), not a DOM element. It can extend past the webview frame in any direction. Don't build a custom Tauri overlay window for tooltip-like content — the browser already does it for free, with correct hit-testing, no focus issues, and no capability concerns. The trade-off is plain text only (no styling, no highlighting).

**Dynamically created windows have no IPC**: `WebviewWindowBuilder::build()` creates windows that load and render HTML/JS normally, but `invoke()` calls silently fail — no errors, no logs, just dead IPC. `initialization_script` globals also don't survive to page JS. `WebviewUrl::App("other.html".into())` for non-root HTML files produces a completely empty window (no content, no close button response). The workaround: pre-configure windows in `tauri.conf.json` with `visible: false`, then show/hide them via commands. Pre-configured windows get full IPC. Use a managed state + events to pass data between windows (e.g. `HistoryTarget` mutex + `history_target` event). For the OS close button on reusable windows: match `CloseRequested { api, .. }`, call `api.prevent_close()`, then `window.hide()`.

## Managed state timing: `.setup()` vs `Builder::manage()`

Commands using `State<T>` where T is managed inside `.setup()` can consistently fail with `"state not managed for field 'state' on command 'get_config'"`. The webview (pre-configured in `tauri.conf.json`) can invoke commands before `.setup()` completes — this is not a rare race, it reproduces on every launch.

- **`Builder::manage()`** (before `.setup()`) — state is always available to commands from the first `invoke()`.
- **`app.manage()` inside `.setup()`** — state may not be available when the webview's JS first executes `onMount` / startup code.

Fix: for state that must be constructed inside `.setup()` (needs `app.path()`, config files, etc.), change the command from `State<T>` to `AppHandle` and use `try_state`:

```rust
#[tauri::command]
pub fn get_config(app: AppHandle) -> Config {
    app.try_state::<ConfigState>()
        .map(|s| s.snapshot())
        .unwrap_or_default()
}
```

The frontend gets a default config on the first call, then receives the real config via the `config_updated` event once setup finishes and the config watcher fires. If your type doesn't implement `Default`, return `Option<T>` and handle `None` in the frontend.
