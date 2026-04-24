---
name: Warp cursor when clamping a drag-tracked element
description: When a drag-clamped element stops at a boundary, also warp the (hidden) cursor to the clamped position so the user doesn't back-track the overshoot.
type: feedback
---

In a custom drag implementation that hides the cursor and moves an element to track it, when the cursor goes past a clamp boundary and you pull the element back, also warp the cursor to the clamped position. Otherwise the user has to drag the cursor all the way back through the overshoot before the element moves in the opposite direction — which feels broken.

**Why:** Without the cursor warp, "cursor past boundary + element clamped" is a stable state. The user moves the cursor toward center; the element stays clamped until the cursor crosses back through the original tracking point. The longer the overshoot, the longer the dead zone. Identified during crop-stage frame-drag clamp work — the user noticed it immediately and called it confusing.

**How to apply:**
- Detect the clamp condition in the same handler that updates the element's position.
- After pulling the element back, warp the cursor to the element's tracking point (e.g. `SetCursorPos` on Windows).
- Only do the warp while the drag is active (e.g. mouse capture held); outside drag, moving the cursor would be unexpected.
- The cursor is typically already hidden during such drags, so the warp is invisible.
