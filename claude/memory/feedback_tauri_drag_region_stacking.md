---
name: Tauri drag regions don't propagate through overlapping children
description: `data-tauri-drag-region` only applies to the element directly under the cursor — absolute-positioned overlays intercept drag unless tagged or set to pointer-events:none
type: feedback
---

Tauri v2's `data-tauri-drag-region` is checked against the element the OS hit-tests — not its ancestors. For a draggable region with absolutely-positioned children on top (progress fill overlays, tooltip text, badges, decorative icons), the children intercept the drag unless they either:

1. Carry `data-tauri-drag-region` themselves, OR
2. Have `pointer-events: none` so events pass through to the parent that does.

**Why:** Discovered while building the tauri-dashboard widget — the widget header was marked draggable, but dragging over the filled portion of a progress bar did nothing. Root cause: a `.fill` div was absolutely positioned on top of the track, intercepted the mousedown, and had neither the drag attribute nor `pointer-events: none`. Marking the parent drag region wasn't enough — Tauri only sees the topmost hit-test target.

**How to apply:** when retrofitting drag behavior onto composed components (progress bars, pills with badges, labels with icons), audit every child at hit-test depth. Easiest rule of thumb: mark `data-tauri-drag-region` on every descendant that's non-interactive, OR put `pointer-events: none` on purely decorative children. Keep interactive children (buttons, links, inputs) as normal — they shouldn't be drag surfaces anyway.

Applies equally to frameless windows with custom titlebars, transparent windows, and any Tauri window using `decorations: false` with `data-tauri-drag-region` for repositioning.
