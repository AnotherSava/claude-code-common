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
