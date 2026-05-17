# build123d Pencil API quirks

The project's `Pencil` class (`src/sava/csg/build123d/common/pencil.py`) is a 2D drawing tool that builds profiles via lines/arcs for later extrusion. Several of its method names suggest "move without drawing", but **every operation draws a line**.

## All operations draw

- `jump(destination)` — interpreted as **relative displacement** from current location. Adds a `Line(current, current + destination)` to the path. Does NOT just move the pen.
- `jump_to(destination)` — same but the argument is an **absolute** position.
- `down(length=None)` — draws straight down. With no arg, draws to `y=0`. With `length`, draws by that much downward.
- `left(length)`, `right(length)`, `up(length)` — draw lines along the corresponding axis.
- `draw(length, angle_deg)` — draws a line of `length` at `angle_deg` (degrees from +X).
- `arc_with_destination(destination_rel, angle_deg)` — draws an arc to `current + destination_rel` with the given **sweep angle** (NOT radius). Radius is derived from chord length + sweep angle.

There is **no** "move without drawing" operation. If you need that, restructure the pencil sequence so the move corresponds to a real edge in your polygon.

## Auto-close

When `pencil.extrude(...)` is called, the path is closed back to the pencil's starting position (default `(0, 0)`) by an implicit final edge. This means a Pencil with N visible operations produces a polygon with N+1 edges (if the path didn't already return to start).

## Common gotcha

Reading `back_protrusion.jump((1.366, 1.7))` as "move the pen to (1.366, 1.7)" produces wrong results — it draws a line from the current location (e.g., origin) to that offset. The first edge of the polygon will be a slanted line, not just a positioning step.

## Example

```python
back_protrusion = Pencil()
back_protrusion.jump((1.366, 1.7))   # edge 1: (0,0) → (1.366, 1.7)  (slanted)
back_protrusion.left(17)              # edge 2: (1.366, 1.7) → (-15.634, 1.7)
back_protrusion.down()                # edge 3: (-15.634, 1.7) → (-15.634, 0)
# auto-close on extrude:               edge 4: (-15.634, 0) → (0, 0)
back_protrusion_body = back_protrusion.extrude(1.5)
```

Final polygon has 4 vertices: `(0,0)`, `(1.366, 1.7)`, `(-15.634, 1.7)`, `(-15.634, 0)`.

## Arc sweep angle is degrees, not radians

`arc_with_destination(dest, angle)` takes `angle` in **degrees** as the sweep angle. Sign convention: positive = CCW arc, negative = CW. The radius is computed from `chord_length / (2 · sin(angle/2))`.

Angles are preserved under uniform scaling (linear scaling preserves angles), so when scaling Pencil paths, only multiply the coordinate tuples — leave the angle parameters alone.
