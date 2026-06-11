# Tauri: mixed-DPI window sizing (scale_factor vs devicePixelRatio)

On a multi-monitor setup with different per-monitor scale factors (e.g. a 1.0× external + a 1.5× laptop panel), **Rust's `window.scale_factor()` and the webview's `window.devicePixelRatio` can disagree** for the same window — especially while the window sits near or crosses a monitor boundary. They can report the scale of *different* monitors: Windows assigns a window's DPI by the monitor it mostly overlaps, while the webview may still be rendering at the previous monitor's DPR until it fully transitions.

## Symptom

A content-fit / auto-resize scheme that:

1. measures content height in CSS px on the frontend,
2. sends a *logical* height to Rust, and
3. has Rust call `set_size(LogicalSize(height))` (which multiplies by `scale_factor()` internally)

…lands the webview viewport at the wrong physical size whenever the two scales differ. The viewport never equals the requested height, so an "is content taller than the viewport?" overflow check stays true forever → the resize re-fires endlessly, and any per-call `set_position` nudges the window so it drifts across the screen (often marching diagonally toward a monitor corner and converging there).

The asymmetry tell: if the second monitor is *below* the primary, a "grow downward" mode walks into it while "grow upward" stays clear — so only one direction misbehaves.

## Fix

Size in **physical pixels derived from the webview's own `devicePixelRatio`**, bypassing Rust's `scale_factor()` for the size path entirely:

```ts
// frontend — measure in CSS px, convert with the webview's OWN dpr
const physical = Math.round(contentCssHeight * window.devicePixelRatio)
invoke('apply_resize', { physicalHeight: physical })
```

```rust
// Rust — use PhysicalSize; do NOT multiply by window.scale_factor()
window.set_size(PhysicalSize::new(width_phys, physical_height.round() as u32))?;
```

Because both the measurement and the applied size now use the *webview's* DPR, the viewport lands exactly on the content regardless of what Rust thinks the scale is. The overflow check clears and the loop terminates.

## Diagnosis

Log both sides for the same resize: Rust's `scale_factor()` and the frontend's `devicePixelRatio`. When they differ for one window, you've found the mismatch. Also log the resulting `window.innerHeight` against the requested height — if `innerHeight` falls short, the size path used the wrong scale.

## Related guards (frameless windows)

- A frameless window's `outer_position()` round-trip can be slightly inconsistent across DPI, so a redundant `set_position` call nudges the window. Guard it: only `set_position` when the target differs from the current position.
- Don't react to your own resize: a short cooldown that ignores the `resize` event fired by your own `set_size` prevents a self-perpetuating measure → resize → measure loop. (Necessary but not sufficient on its own — it slows a DPI-mismatch loop from a tight burst to a slow trickle, but only the physical-px fix above stops it.)
