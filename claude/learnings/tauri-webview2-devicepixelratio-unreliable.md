# WebView2 devicePixelRatio is unreliable for window sizing

On Windows mixed-DPI multi-monitor setups, `window.devicePixelRatio` in a Tauri/WebView2 frontend intermittently misreads (e.g. `1.5→1.0` on a 150% monitor) and **holds the wrong value for tens of seconds** before flipping back — it is *not* a sub-second flicker. That means a persistence/hysteresis filter ("adopt a changed reading only after it holds for N ms") cannot reliably distinguish the misread from a genuine monitor DPI change: the bad value outlives any reasonable window and gets adopted as stable.

## Why it bites

If you convert a CSS-px content measurement to physical px with this value:

```
physical = css_measurement × window.devicePixelRatio
```

a low misread lands a collapsed physical size. In the claude-code-dashboard auto-resize widget, `devicePixelRatio` reading `1.0` instead of `1.5` shrank a ~219px window to ~70 logical px (a header sliver). Measured on ~9% of sizing passes over the log history. The window self-heals only when a later content change happens to re-measure while dpr reads correctly, so it looks intermittent and is easy to misattribute to a race or a flicker.

## Fix: source the scale from the OS, not the webview

Rust's `window.scale_factor()` (winit → OS `GetDpiForWindow` on Windows) reads the OS per-monitor DPI and is **stable across the JS-side flap**. Don't trust the webview's `devicePixelRatio` for the conversion factor at all:

- Have the resize command **return** `window.scale_factor()`, and/or expose a dedicated getter the frontend calls once at mount to seed the value.
- The frontend holds the last backend-reported scale and sizes against it (`physical = css × backendScale`), refreshing it on every command reply. A genuine monitor DPI change lands within one measure; a transient webview misread never enters the math.
- CSS-px layout is dpr-independent, so the content measurement (`getBoundingClientRect()`) stays correct regardless of the misread — only the conversion factor needed a trustworthy source.

## Keep the raw reading for diagnostics

Log both the scale you actually used and the raw `devicePixelRatio` (`dpr` vs `raw_dpr`). After the fix they diverge exactly when a misread occurs — `raw_dpr:1` beside `dpr:1.5` with a correct physical size — which is a built-in regression detector: a collapse would show them agreeing on the wrong value again.

## Note on the physical-vs-logical protocol

Sizing in physical px (frontend multiplies, sends physical) rather than logical px (send logical, let Rust multiply by its own `scale_factor()`) is a deliberate choice in that project: near a mixed-DPI monitor boundary Rust's `scale_factor()` and the webview's render dpr can disagree, and applying a logical height under Rust's scale lands the viewport at the wrong size (false-overflow → scrollbar → re-triggering measure loop → window drifts across monitors). Sourcing the scale from the OS keeps the physical-px protocol *and* removes the flaky `devicePixelRatio` — you get both.

(Discovered in the claude-code-dashboard auto-resize widget; the project-specific writeup is the `auto_resize_dpr_flicker_collapse` project memory. Related: `tauri-webview2-cache-staleness`, `tauri-windows-native`.)
