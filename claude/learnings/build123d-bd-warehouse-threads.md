# bd_warehouse threads in build123d models

Behaviour of `bd_warehouse.thread.IsoThread` and `Thread` measured while modelling a screw-on cap for a 10 mm
tube thread (bd_warehouse as installed in a build123d 0.10-era venv, 2026-10-30).

## Cut an internal thread with an external bolt

The pattern "cut a hole of the major diameter, then fuse an internal `IsoThread` (`external=False`) into it"
added zero volume in one model: the ring's volume was identical before and after `fuse`, so the printed part
had a smooth bore. The same pattern is used elsewhere without anyone noticing a problem, so treat it as
unreliable rather than always broken, and verify it by volume or by a cross-section, never by eye.

The robust alternative is to build the negative and cut it. `SmarterCone` and `SmartSolid` below are the
build123d-models project's wrappers; in plain build123d the core is a `Cylinder`, and the fuse and cut are `+`
and `-`:

```python
thread = Thread(apex_radius=major / 2, apex_width=groove_width, root_radius=minor / 2,
                root_width=pitch - ridge_width, pitch=pitch, length=length, end_finishes=("fade", "raw"))
core = SmarterCone.cylinder(thread.root_radius, length + pitch)
bolt = core.fuse(SmartSolid(thread))
part.cut(bolt)
```

The bolt's core is the part's crest (minor) diameter, and its thread teeth carve the grooves. Each of
`Thread`'s parameters then names a feature of the printed internal thread directly:

| `Thread` parameter | Feature of the cut internal thread |
|---|---|
| `apex_radius` | groove bottom (major radius of the mating screw + clearance) |
| `apex_width` | groove width at its bottom |
| `root_radius` | ridge crest (minor radius of the mating screw + clearance) |
| `pitch - root_width` | ridge width at its crest |

`IsoThread` fixes depth and widths from the pitch, which yields a thread shallower than many real moulded
threads (a 1.4 pitch ISO external thread reaches about Ø8.3 on a Ø10 major, where the measured tube was
Ø7.9). `Thread` takes any depth.

## The solid's z-extent is not `length`

The bounding box depends on `end_finishes`. Measured for an `IsoThread` of Ø10, pitch 1.5, `length=7`, on bd_warehouse
0.1.1 with build123d 0.10.0 (re-measured 2026-10-31):

| `end_finishes` | z range |
|---|---|
| `("square", "square")` | 0 .. 7.0 |
| `("fade", "fade")` | 0.19 .. 6.81 |
| `("fade", "square")` | 0.19 .. 8.31 |
| `("fade", "raw")` | 0.19 .. 8.31 |
| `("raw", "raw")` | -1.31 .. 8.31 |

A square far end stops at `length` after a square near end, `("square", "square")` ending at 7.0, but after a
fading near end it overshoots to 8.31 exactly as `raw` does. That row is measured, not a copy slip.

So never place a thread by aligning its bounding box. Build it in its native frame together with a cylinder
of known height, and align that cylinder. A `raw` end overshoots by roughly one pitch, which is useful on a
cutter, since the overshoot runs out of the part's opening and keeps the thread full up to the rim.

## A square end against a coplanar face breaks the boolean

Fusing an internal thread whose `square` end lay exactly on the floor of the hole returned an empty
`ShapeList` with no error. `fade` and `chamfer` ends fused cleanly. Avoid coplanar end faces: overshoot with
`raw`, or keep a fading end clear of the wall.

## Clearance for printed threads

A clearance added to the diameter gives almost no axial play when the flanks are steep, since the play
along the axis is roughly the radial clearance times tan of the flank half-angle. A cap with 0.2 mm
diametral clearance and 45° flanks jammed within half a turn. What freed it was narrowing the ridge (0.2 mm
at the crest) and widening the groove bottom (0.2 mm), together with 0.4 mm diametral clearance.

When the pitch cannot be measured (two or three visible crests on a small white thread), print a set of
short threaded rings at candidate pitches, each marked by a count of notches on its rim, and pick the one
that screws on furthest. Over two engaged turns a 0.1 mm pitch error accumulates to 0.2 mm, which alone
jams a tight thread.
