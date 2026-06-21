# Tauri: recovering a window stranded off-screen by a monitor change

A persisted window position (`set_position(PhysicalPosition)` from saved config) restored after the monitor layout changed — external display unplugged, dock removed, resolution/DPI change — can land entirely in dead space off every connected screen. The window is shown but invisible, and immovable because its drag region is off-screen too.

## The trap: `is_visible()` stays `true`

A tray "Show/Hide" that toggles on `window.is_visible()` can't rescue it: an off-screen window still reports `is_visible() == true`, so the toggle just hides it, then re-shows it in the same unreachable spot. Symptom the user reports: **"show/hide does nothing."**

## Fix: validate the restored rect against `available_monitors()`

On startup (after restoring a saved position) and on every show path (tray toggle, frontend `show_window`), check whether the window's outer rect overlaps any monitor's **work area** by a grabbable margin (~64px per axis, or the window's own span if smaller — a thin sliver isn't reachable). If not, clamp it onto the monitor it overlaps most (primary as fallback) and `set_position` it back.

Key APIs: `window.available_monitors()` → `Vec<Monitor>`, `monitor.work_area()` (excludes taskbar/dock), `window.primary_monitor()`. Work-area overlap + clamp logic is unit-testable if extracted from the live `Monitor` type into a plain bounds struct.

A window that was on-screen also keeps its physical coordinates across a live monitor unplug, so the show-path check (not just startup) is what makes manual recovery possible without a relaunch.
