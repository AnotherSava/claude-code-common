# build123d: `.orientation` rotates around `Location.position`, not the geometric centre

## Discovery

In the build123d-models project, the `SmartBox(L, W, h)` wrapper around `Solid.make_box` was producing wildly displaced geometry after any `.rotate_z` call. Tracing the bug led to two interacting facts:

1. **SmartBox's Z-base-aligned construction** leaves a non-identity Location. The constructor:

   ```python
   solid = Solid.make_box(L, W, h).move(Location((-L/2, -W/2, 0)))
   ```

   centers the box in XY and base-aligns it in Z (`X[-L/2, L/2], Y[-W/2, W/2], Z[0, h]`). The translation is captured in the Solid's `Location.position`, which becomes `(-L/2, -W/2, 0)` — NOT baked into the vertex coordinates.

2. **`solid.orientation = (a, b, c)` rotates around `Location.position`.** Not around world origin. Not around the solid's geometric centre. Setting orientation on a moved Solid pivots the rotation through the moved Location.

Combined effect: every `SmartBox(...).rotate_z(angle)` rotates the box around a point on its edge (the Location's corner-offset position), visibly displacing it instead of spinning it in place. Symptoms include a 39×2×1.5 slot bbox center moving from `(0, 0, 0.75)` to `(-14.12, -19.77, 0.75)` after a 90° rotation.

## Fix

Construct on a shifted plane so the Location stays at identity:

```python
solid = Solid.make_box(L, W, h, plane=Plane(origin=(-L/2, -W/2, 0)))
```

The geometry occupies the same world coordinates, but `Location.position` is `(0, 0, 0)` afterwards. Orient then rotates around world origin (which coincides with the box's XY center, base at Z=0).

## General rule

Whenever a build123d Solid will be passed to code that sets `.orientation`, ensure its `Location.position` is at the correct rotation pivot. Pre-set the geometry via the `plane` argument on construction, or `Pos((cx, cy, cz)) * solid` patterns that don't shift Location. Avoid `.move(Location((dx, dy, dz)))` immediately before orient — the dx/dy/dz become the unintended pivot.

## Avoiding orient entirely

For arbitrary-axis rotation, bypass orient and use `gp_Trsf.SetRotation` directly:

```python
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
from build123d import Location
from math import radians

trsf = gp_Trsf()
trsf.SetRotation(
    gp_Ax1(gp_Pnt(*pivot_xyz), gp_Dir(*axis_dir)),
    radians(angle_deg),
)
solid = solid.moved(Location(trsf))
```

This is immune to Location offsets — the pivot is specified explicitly and the rotation is applied directly to the geometry, with the Location updated as a side-effect. The build123d-models project uses this pattern in `SmartSolid.rotate` for the off-origin-axis branch.

## Caveat for subclass polymorphism

Wrapper classes (e.g. `SmartLoft`, `SweepSolid` in this project) override `orient()` to also re-orient subsidiary objects (profiles, paths). If you bypass orient via `gp_Trsf`, those subsidiary objects won't be updated. Acceptable when the rotation is on the assembled solid only; otherwise the subclass needs its own rotate override that propagates the same `gp_Trsf` to subsidiary objects.

## Boolean ops and transforms also reset `Location.position`

The corner-anchor case isn't the only way `Location.position` drifts. Every OCC boolean op and a couple of transforms produce a *fresh* shape with `location.position = (0, 0, 0)`, regardless of where the inputs were:

- `shape1 + shape2` (OCC fuse, used by `SmartSolid.fuse`)
- `shape1 - shape2` (OCC cut, used by `SmartSolid.cut`)
- `shape1 & shape2` (OCC intersect)
- `mirror(shape, plane)`
- `scale(shape, factors)`

The world geometry of the result *is* placed correctly (the BRep encodes the world positions of the boolean's output), but any tracked-anchor field separate from `location.position` (e.g. SmartSolid's `self.origin`) silently drifts out of sync. Code that reads `solid.origin` after a fuse to find "where the shape is" gets the *pre-fuse* anchor, not anything geometrically meaningful.

Pencil-built shapes (e.g. `pencil.extrude_mirrored_y(h)`) are well-behaved — the constructor produces `Location.position = (0, 0, 0)` matching SmartSolid's `__init__` default.

Edge case: disjoint OCC fuse returns a `ShapeList`, not a single Shape. `ShapeList` has no single `.location`, so any "reanchor" logic must early-out for it.

## The `relocate` API

`build123d.Shape.relocate(loc)` is **the only API that changes `Location.position` without moving world geometry**. It does so by baking the inverse transform into the BRep via `BRepBuilderAPI_Transform`, then setting the location:

```python
shape.relocate(Location(Vector(target_x, target_y, target_z), shape.location.orientation))
```

`relocate` is marked deprecated in current build123d ("use `move`, `moved`, `locate`, or `located` instead") but the suggested alternatives all *move* world geometry — they don't cover this use case. Empirically verified:

| Method | Effect on `location.position` | Effect on world geometry |
|---|---|---|
| `move(loc)` | += `loc.position` (composes) | shifts by `loc.position` |
| `locate(loc)` | = `loc.position` (absolute) | shifts to match new location |
| `relocate(loc)` | = `loc.position` (absolute) | **unchanged** |

Suppress the `DeprecationWarning` for legitimate "rebrand the anchor" uses:

```python
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    shape.relocate(Location(target_position, shape.location.orientation))
```

## The invariant approach (build123d-models `SmartSolid._reanchor`)

An alternative to the `gp_Trsf` bypass: maintain a class invariant `self.origin == self.solid.location.position` so `orient()`'s location-anchored pivot always coincides with the user-facing anchor. Then the standard `R(θ)·origin − origin` translation correctly re-anchors to the world axis line.

Pattern (see `src/sava/csg/build123d/common/smartsolid.py`):

```python
def _reanchor(self):
    """Sync self.solid.location.position to self.origin without moving world
    geometry. No-op for ShapeList (no single location)."""
    if self.solid is None or isinstance(self.solid, ShapeList):
        return self
    current = Vector(self.solid.location.position)
    target = Vector(self.origin)
    if (current - target).length < 1e-10:
        return self
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        self.solid.relocate(Location(target, self.solid.location.orientation))
    return self
```

Called in `__init__` (fixes raw `Box(L,W,H)` corner anchoring) and after `fuse/cut/intersect/mirror/scale/pad` (which reset `self.origin = Vector(0, 0, 0)` then `_reanchor`).

Trade-off vs the `gp_Trsf` bypass:
- ✅ The standard `orient()`-based `rotate` works without per-method pivot logic; subclasses' `super().rotate()` calls work polymorphically.
- ✅ Other code that needs the invariant (e.g. `rotate_multi` with the same latent pivot bug) is fixed simultaneously.
- ❌ `self.origin` resets to `(0, 0, 0)` after boolean ops / mirror / scale — it no longer tracks the pre-op anchor through these. Use `bound_box.center()` for "where is this shape" queries.

## Latent double-rotation bug if `_orientation` isn't reset alongside `origin`

Maintaining `_reanchor()` for `location.position` after OCC boolean ops is necessary but not sufficient. The OCC primitives also reset `solid.orientation` to identity (the rotation is baked into the BRep coordinates), so any tracked cumulative orientation field (e.g. SmartSolid's `self._orientation`) also needs resetting. Otherwise:

```python
a = SmartBox(4, 4, 4).move(20, 0, 0)
a.rotate_z(90)         # _orientation = (0, 0, 90), solid.orientation = (0, 0, 90)
a.fuse(...)            # solid.orientation resets to (0, 0, 0) (BRep encodes the rotated geometry)
                       # but _orientation stays at (0, 0, 90) — DESYNCED
a.rotate_z(0)          # orient() sets solid.orientation = _orientation = (0, 0, 90)
                       # → rotates the already-rotated geometry a SECOND time
```

Fix: reset both fields together in every OCC-op wrapper:

```python
self.origin = Vector(0, 0, 0)
self._orientation = Vector(0, 0, 0)
self._reanchor()
```

## Builder rebuilds: the dual problem

Builder-pattern subclasses (e.g. `SmarterCone` with its `extend`/`inner` methods) do the opposite: `_build_solid()` produces an *unrotated* fresh solid every time it's called. If a user did `rotate_z(80)` between `inner()` and `extend()`, the `extend()` rebuild would silently discard the rotation from `self.solid` (even though `self._orientation` still holds the value).

This breaks alignment-style mid-build inspection: `print(s.bound_box)` between rebuild and next transform shows unrotated geometry; `align_x()` would compute its delta against the unrotated bbox.

Fix: after every `_build_solid()`, replay the tracked state:

```python
def _apply_tracked_transforms(self) -> 'SmartSolid':
    if self.solid is None or isinstance(self.solid, ShapeList):
        return self
    if self._orientation.length > 1e-10:
        self.solid.orientation = self._orientation   # rotates around location.position == (0,0,0)
    current_pos = Vector(self.solid.location.position)
    if (current_pos - self.origin).length > 1e-10:
        self.solid = self.solid.moved(Location(tuple(self.origin - current_pos)))
    return self
```

This is the *dual* of `_reanchor`: `_reanchor` keeps world geometry while syncing tracked state to it; `_apply_tracked_transforms` keeps tracked state while syncing world geometry to it. Boolean ops use `_reanchor` (BRep already encodes the world state); builder rebuilds use `_apply_tracked_transforms` (BRep is identity, tracked state holds the truth).

Pattern: every method that replaces `self.solid` needs to pick one. Boolean ops → reset state + `_reanchor`. Builder rebuilds → keep state + `_apply_tracked_transforms`.

Result: builder calls commute with `rotate()`/`move()` — `extend → rotate` and `rotate → extend` produce identical world geometry.
