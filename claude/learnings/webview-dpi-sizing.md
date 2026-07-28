# Sizing a frameless webview window to its content on mixed-DPI

When a desktop app (Tauri, Electron, any native shell hosting a webview) auto-resizes a **frameless** window to fit its rendered content, it measures the content in CSS pixels and must convert to physical pixels to set the window size: `physicalHeight = cssContentHeight * scale`. On a mixed-DPI multi-monitor setup, picking the wrong `scale` collapses or oversizes the window. This is a recurring, easy-to-misdiagnose trap.

## The two scale signals, and how each lies

There are two ratios you can reach for, and **neither is reliable alone** — worse, from a single `(devicePixelRatio, scale_factor)` pair you cannot tell which one is currently wrong:

- **`window.devicePixelRatio`** (the webview's JS reading): the ratio the webview *actually rasterizes at*. It's correct by construction for content-fit — `cssHeight * devicePixelRatio` is the physical footprint the content occupies — and it **tracks the window moving to a different-DPI monitor**. Its one flaw: a brief mount-time transient where it can read `1.0` for ~2s on a 150% monitor before settling to the true `1.5`.
- **The native/OS per-monitor scale** (e.g. Tauri Rust `window.scale_factor()`, Win32 `GetDpiForWindow`): stable, but typically **read at window creation and goes stale** — it does *not* update when the window later lands on a different-DPI monitor. Observed: after a relaunch onto a 150% monitor, `scale_factor()` stayed stuck at `1.0` for 35+ minutes while `devicePixelRatio` correctly settled to `1.5`, so sizing against `scale_factor()` produced a window sized at `1.0` that clipped the `1.5`-rendered content to a sliver.

Trusting either one exclusively fixes the setup you tested and breaks another. (Real history: a hysteresis filter on `devicePixelRatio` failed, then switching to the native scale failed the opposite way.)

## The fix: size against devicePixelRatio, and guarantee a re-measure on every DPR change

The real root cause of the stuck-collapse in **both** directions is not "which scale to trust" — it's that **a scale change must re-fire a measure**. Once you re-measure whenever the ratio changes, `devicePixelRatio` becomes the right choice: it reflects reality and self-corrects.

1. Size with `window.devicePixelRatio` (fall back to `1` if `0`/unavailable).
2. Re-measure on every DPR change. A window `resize` event usually fires on a DPI change (WM_DPICHANGED resizes the window), but not always — so add an explicit listener:

```js
// Re-armed per change: the query string pins the current ratio, so it stops
// matching the moment devicePixelRatio changes, firing 'change'.
let dprMedia = null
function armDprListener() {
  dprMedia?.removeEventListener('change', onDprChange)
  dprMedia = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`)
  dprMedia.addEventListener('change', onDprChange)
}
function onDprChange() {
  armDprListener()   // re-arm for the next change
  scheduleMeasure()  // debounced re-measure
}
armDprListener()
// cleanup: dprMedia?.removeEventListener('change', onDprChange)
```

This makes the ~2s mount transient self-heal (one provisional small measure, corrected the instant DPR settles) and handles monitor-to-monitor moves that the native scale would miss.

## Guardrails that made diagnosis and robustness easier

- **Send physical pixels to the native side; don't hand it a logical height to scale.** Near a mixed-DPI boundary the native scale and the webview DPR disagree, so a logical request lands at the wrong physical size (false overflow → scrollbar → a re-triggering measure loop that drifts the window across monitors).
- **Log both ratios on every measure** (`dpr` used, `devicePixelRatio` raw, and the native `scale_factor`). When they disagree, the trace tells you instantly which one went stale — a built-in regression detector for the next time this resurfaces.
- The overflow check `contentCssHeight > innerHeightCss` is **scale-free** (both sides are CSS px), so it detects "too short" without trusting any ratio — a good backstop signal, though the *correction* still needs a scale.
- Guard the width axis separately (a `minWidth` floor), since auto-resize usually only drives height.

## Debugging gotcha: an external probe reads a VIRTUALIZED window size

When you verify the window's real pixel size from a **separate** process (a PowerShell script, a debug tool), `GetClientRect`/`GetWindowRect` return **DPI-virtualized** coordinates — scaled by `96/os_dpi` — unless that probe process is itself per-monitor-DPI aware. Windows PowerShell launches DPI-unaware, so on a 144-DPI (1.5×) monitor a correct **158-physical** window reads back as **105** (`158 × 96/144`), faking a "window is a row too short / scrollbar" bug on a window that is actually sized perfectly. This can send you down an elaborate wrong diagnosis (it did — 2026-07 on the claude-code-dashboard widget).

Fix the probe: call `SetThreadDpiAwarenessContext((IntPtr)-4)` (`PER_MONITOR_AWARE_V2`) before `GetClientRect`; confirm with `GetAwarenessFromDpiAwarenessContext(GetThreadDpiAwarenessContext())` (`0`=unaware, `1`=system, `2`=permonitor). Note `GetDpiForWindow` is **not** virtualized — it returns the true per-monitor DPI regardless of caller awareness, so an honest `GetDpiForWindow` beside a shrunken `GetClientRect` is itself the tell. Best of all, trust the app's own signals: the webview's `innerHeight` (CSS px, never virtualized) and a Rust-side `GetClientRect` read from *inside* the per-monitor-aware app process (true physical px) — log the latter next to the requested height in the resize path so requested-vs-actual is greppable.

## Related Chromium/WebView2 note

`window.devicePixelRatio` not updating until a reflow after a monitor/DPI change is a known Chromium class of bug; the `matchMedia('(resolution: …)')` re-arm is the standard, battle-tested way to observe DPR changes (it also catches browser zoom). It also **throttles while the window is occluded/suspended** — the `WM_DPICHANGED` paint that carries the DPR update and fires the `matchMedia` `change` can lag until the window is next foregrounded/repainted, so a DPI change absorbed while hidden may not re-fire a measure on its own (a `visibilitychange`/`focus` re-measure is the documented fallback).
