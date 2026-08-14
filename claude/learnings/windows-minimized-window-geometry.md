# Windows: a minimized window reports the iconic rect, not its own geometry

When a window is minimized, Win32 stops answering geometry queries about the *window* and starts answering about its **iconic placeholder**. Any code that reads position/size to compute a new position/size — an auto-fit, an anchored resize, an off-screen rescue, a "save my geometry on close" — silently operates on numbers that have nothing to do with the real window.

This bites hardest for always-on-top widgets, because a full-screen application (typically a game) minimizes them without the user doing anything, and the app keeps running and keeps recalculating.

## What the OS actually returns while iconic

Measured on a frameless, resizable, `WS_EX_TOOLWINDOW` window at 144 DPI (`GetSystemMetricsForDpi`):

| Query | Normal | Minimized |
|---|---|---|
| `GetWindowRect` position | real | `(-32000, -32000)` |
| `GetWindowRect` size | real | `237x39` == `(SM_CXMINIMIZED, SM_CYMINIMIZED)` |
| `GetClientRect` | real | `215x26` — the iconic rect minus the frame |
| `IsWindowVisible` | true | **true** — minimizing never clears `WS_VISIBLE` |
| `IsIconic` | false | true |
| `WINDOWPLACEMENT.rcNormalPosition` | real | **real** — preserved |

Two consequences that look like bugs elsewhere:

- `(-32000, -32000)` overlaps no monitor, so **a minimized window always looks "stranded off-screen"** to any work-area overlap check. An off-screen rescue therefore misfires on every show-while-minimized and writes a position derived from the icon.
- `GetClientRect` returns iconic-minus-frame, not zero, so a plausible-looking small number reaches your layout math. (It *does* return `0x0` when the frame plus caption exceeds the iconic height — so a captioned window and a frameless one disagree here. Don't key logic on the specific value.)

## Writing geometry while iconic is harmless — but pointless

Verified experimentally: `SetWindowPos` with tao's flag sets (`SWP_ASYNCWINDOWPOS | SWP_NOZORDER | SWP_NOREPOSITION | SWP_NOMOVE | SWP_NOACTIVATE` for a resize, `…| SWP_NOSIZE` for a move) applied to a minimized window leaves `rcNormalPosition` untouched, and the window restores to exactly its pre-minimize rect. So the corruption risk is not "the write lands wrong"; it's that **you computed a value from garbage inputs and may apply it later**, and that you persist garbage if you save geometry at that moment.

Guard the *reads*. Don't bother trying to make the writes safe.

## `SW_SHOW` does not un-minimize

`ShowWindow(hwnd, SW_SHOW)` on an iconic window "displays it in its current state" — i.e. still iconic. Revealing a minimized window as a header-height strip is the classic symptom. Use `SW_RESTORE`, or in Tauri `window.unminimize()` **before** `show()`. Related: `SetFocus`/`set_focus` no-ops on a minimized window, so a "bring to front and tell the frontend something" path silently talks to a window nobody can see.

## Detection and the restore edge (tao / Tauri v2)

- `tao::Window::is_minimized()` → `IsIconic(hwnd)` directly. Authoritative: it works even when a *third party* minimized you, which a cached flag would miss (tao's own `WindowFlags::MINIMIZED` only updates from `WM_SYSCOMMAND` `SC_MINIMIZE`/`SC_RESTORE`, so it does **not** see a game's `ShowWindow(SW_MINIMIZE)`).
- There is no `Minimized`/`Restored` window event. `WM_SIZE` fires for both edges and tao emits `WindowEvent::Resized` unconditionally for every one of them (with `w/h == 0` on minimize). Fold the stream to the edge you want:

```rust
static WAS_MINIMIZED: AtomicBool = AtomicBool::new(false);

fn resized_is_restore(window: &WebviewWindow) -> bool {
    let now = window.is_minimized().unwrap_or(false);
    let was = WAS_MINIMIZED.swap(now, Ordering::SeqCst);
    was && !now
}
```

Acting on every `Resized` instead of the edge loops, because your re-fit resizes the window, which emits another `Resized`.

## Gate on minimized, never on "not visible"

A window hidden to the tray keeps a **real** rect. Suppressing geometry work whenever the window isn't visible means it comes back stale after every tray toggle. `is_minimized` and `is_visible` are independent — and as the table shows, a minimized window reports itself visible anyway.

## The webview does not learn about any of this

Minimizing does not resize a hosted WebView2/WKWebView child. `window.innerHeight` stays frozen at its pre-minimize value for the whole minimized stretch **and across the restore**. So every frontend self-heal keyed on the viewport (`viewportHeight * 2 < desiredHeight` and friends) reads the window as already fitting and never fires, and a request-based dedup (`desired === lastSent`) swallows the corrective pass afterwards. Recovery has to be driven from native code, which holds the only honest signal, and it must clear the frontend's dedup keys when it asks for a re-measure.

## macOS is not symmetric — and doesn't need to be

A miniaturized `NSWindow` keeps its real `frame`, so the geometry is never corrupted there and the guard is simply inert. tao registers no `windowDidMiniaturize:`/`windowDidDeminiaturize:`, and AppKit doesn't resize a window to miniaturize it (the miniwindow is a separate entity), so **no `Resized` fires on either macOS edge** — a restore-edge re-fit can never run there. That's a non-issue rather than a gap, but don't assume the recovery you tested on Windows is live on macOS.

## Probing it from outside the app

An external probe must declare DPI awareness first or the numbers come back virtualized (divided by the scale factor) and you will chase a bug that isn't there:

```powershell
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
# PerMonitorV2 == -4
[void][W]::SetProcessDpiAwarenessContext([IntPtr](-4))
```

Also declare `GetWindowTextW`/`GetClassNameW` with `CharSet = CharSet.Unicode`; the default ANSI marshalling reads a UTF-16 buffer as ASCII and hands back only the first character, which silently matches the wrong window.

To reproduce the whole failure without a game: `ShowWindow(hwnd, SW_MINIMIZE)` from a separate process is exactly the path a full-screen app takes.
