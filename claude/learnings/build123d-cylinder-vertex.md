# SmarterCone.cylinder vertex sampling

When you sample `cylinder.solid.vertices()` on a `SmarterCone.cylinder(radius, height)`, the result is NOT what you might expect. Each circular cap (top and bottom) contributes exactly **one vertex** — at the parametric seam of the closing edge, not the cylinder's axis center.

## Where the seam is

For a freshly-built cylinder (no rotations applied), the seam vertex is at `+X` direction from the axis at radius distance, on each end cap. So:

```python
pin = SmarterCone.cylinder(radius=1.82, height=4)
# pin axis: (0, 0, 0) to (0, 0, 4)
# Top vertex returned by .vertices(): approximately (1.82, 0, 4)  ← the seam, NOT the center
# Bottom vertex: approximately (1.82, 0, 0)
```

## What "axis center" really means

The cylinder's geometric axis (the imaginary line through the centers of both end circles) is **not represented by any vertex** in the BREP. To find it empirically:

1. **Track total rotation**: after rotations summing to `θ_total`, the seam offset rotates with it. The axis is at `(top_vertex.x - r·cos(θ_total), top_vertex.y - r·sin(θ_total))`.
2. **Sample bbox**: the cylinder's XY bbox is a `2·r × 2·r` square centered on the axis. Useful when the cylinder is isolated.
3. **Sample multiple Z slices**: if you can isolate the cylinder's edges, sampling parametric points along the circular edges and averaging gives the axis center.

## Gotcha that bites

If you sample `top_vertex` thinking it's the axis center and use it to compute a polar angle from the iris/world origin, you get an angle that's off by `atan(r/distance_from_origin)` — small (a few degrees) for far-from-origin cylinders, but enough to cause visible misalignment in assemblies.

This bit me when computing iris cover rotation: blade pin polar was computed from `top_vertex` directly, giving 42.6° instead of the actual axis polar 39.4° — a 3° error in cover rotation. Fix: subtract the seam offset.

## Workaround

```python
# After total rotations summing to TOTAL_ROT_DEG:
total_rot_rad = math.radians(TOTAL_ROT_DEG)
edge_offset = (PIN_RADIUS * math.cos(total_rot_rad), PIN_RADIUS * math.sin(total_rot_rad))
top_vertex = next((v.X, v.Y) for v in blade.solid.vertices() if abs(v.Z - top_z) < 0.01)
pin_axis_xy = (top_vertex[0] - edge_offset[0], top_vertex[1] - edge_offset[1])
```

After a `rotate_z(180°)` (e.g., blade flip), the seam ends up at `-X`, so add `radius` instead of subtracting.
