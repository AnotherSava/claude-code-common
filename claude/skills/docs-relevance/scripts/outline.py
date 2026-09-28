#!/usr/bin/env python3
"""Crop a capture to its subject's outline, with the cut just outside the subject.

    python outline.py <png> [--out PATH] [--tolerance N] [--sides SIDES] [--clean SIDES] [--reach N]

A subject with rounded corners — a dialog, an IDE's island panel, a card — has to be
captured whole: its arcs are in frame, and the background around them is removed by the
frame step's shape mask, never cropped away. That makes where the crop falls a question
the pixels answer, not the component's bounds: the shape's edge is antialiased, so its
outermost pixels are a blend of subject and background, and a crop placed at the border
line, or at bounds measured from the layout, trims that blend off the flats and cuts into
the arcs at the corners.

THE BACKGROUND IS READ OFF THE IMAGE'S OWN EDGE, ROW BY ROW, and the cut goes on the first
pixel that differs from it. A window's backdrop is not one colour — the IntelliJ Islands
frame behind an island carries a tinted gradient — so each row is compared with its own
outermost pixel from the left and from the right, and each column with its own from the
top and the bottom. A pixel more than `--tolerance` levels from that reference, on any
channel, is subject; the crop is the nearest such pixel on each side, so the cut line sits
outside the shape, on its first antialiased pixel. Leave room for that: the capture has to
include some background beyond the subject on every side it is to be cut on.

`--sides` (comma-separated from left, top, right, bottom) names the sides that are the
subject's own outline; the rest are crop cuts through content and stay at the image edge.
Name them whenever the capture cuts through the subject: on a cut side the outermost pixel
is content, and reading "the first pixel unlike it" there would trim into the picture.
`--sides none` is a crop with no outline of its own, for cleaning its cuts alone.

`--clean SIDES` MOVES A CUT OFF THE GLYPHS IT WOULD SLICE. A cut through content leaves a
sliver of whatever straddles it — the first stroke of a letter, a fragment of an icon —
as a small contrast spot against the frame, which reads as a defect rather than as the
edge of a crop. For each side named, the cut is moved inward, by at most `--reach`
pixels, to the nearest line that cuts the fewest glyphs in two: a line between letters, or
between text rows, keeps every glyph on one side of it. A whole glyph that merely touches
the cut is not cut, and a line crossing it scores the same at every candidate, so neither
moves it. The ties go to the smallest move, so a cut that is already clean stays where it
is — which it can only be judged by the line it drops, so run it on a capture that reaches
past every side it cleans. Keep `--reach` inside the gap between the cut and the subject:
the score counts glyphs cut in two, not a border the cut would run along.

A side named by `--clean` is a cut, never the subject's outline, so it is never read off
the pixels: left out, `--sides` defaults to every side `--clean` does not name, and a side
named by both is refused.

The 144-dpi density the published shots carry is kept, as is the colour profile.
"""
from __future__ import annotations

import sys
import textwrap
from itertools import takewhile
from pathlib import Path

from PIL import Image

TOLERANCE = 2


def _first(px, points, tolerance: int) -> int:
    """How far along `points` the first pixel unlike `points[0]` is, or len(points) if none is."""
    ref = px[points[0]]
    for k, p in enumerate(points):
        q = px[p]
        if max(abs(q[i] - ref[i]) for i in range(3)) > tolerance:
            return k
    return len(points)


SIDES = ("left", "top", "right", "bottom")


def outline_box(im: Image.Image, tolerance: int = TOLERANCE, sides: tuple = SIDES) -> tuple:
    """The box, (left, top, right, bottom) with right and bottom exclusive, cut on the subject's first pixel per side.

    Only the `sides` named are read off the pixels; the others are crop cuts and stay at the image edge.
    """
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    left = min(_first(px, [(x, y) for x in range(w)], tolerance) for y in range(h)) if "left" in sides else 0
    right = w - min(_first(px, [(x, y) for x in range(w - 1, -1, -1)], tolerance) for y in range(h)) if "right" in sides else w
    top = min(_first(px, [(x, y) for y in range(h)], tolerance) for x in range(w)) if "top" in sides else 0
    bottom = h - min(_first(px, [(x, y) for y in range(h - 1, -1, -1)], tolerance) for x in range(w)) if "bottom" in sides else h
    if left >= right or top >= bottom:
        raise SystemExit("outline: no pixel differs from the background along any row or column; there is no subject. Nothing was written.")
    return left, top, right, bottom


def _differs(p: tuple, ref: tuple, tolerance: int) -> bool:
    return max(abs(p[i] - ref[i]) for i in range(3)) > tolerance


def _modal(values: list) -> tuple:
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)


def _straddles(px, side: str, box: tuple, e: int, tolerance: int) -> int:
    """How many glyphs an edge at `e` on `side` would cut in two: pixel pairs across it, the last line
    kept and the first dropped, that are both ink.

    Ink is a pixel unlike the modal colour of its own line over the 17 around it, so a line running
    along the cut is background to itself. A line crossing the cut is ink where it crosses, but it
    crosses every candidate alike, so it adds the same to each score and cannot move the choice. An
    inward reference is deliberately not consulted: any stroke longer than half of it — a dash, an
    `=`, the stem of an ascender at a top cut — would read as such a line and score a cut through it 0.
    """
    left, top, right, bottom = box
    if side in ("left", "right"):
        kx, dx = (e, e - 1) if side == "left" else (e - 1, e)
        pairs = [((kx, y), (dx, y)) for y in range(top, bottom)]
    else:
        ky, dy = (e, e - 1) if side == "top" else (e - 1, e)
        pairs = [((x, ky), (x, dy)) for x in range(left, right)]
    kept = [px[k] for k, _ in pairs]
    dropped = [px[d] for _, d in pairs]
    n = 0
    for i in range(len(pairs)):
        window = slice(max(0, i - 8), i + 9)
        if _differs(kept[i], _modal(kept[window]), tolerance) and _differs(dropped[i], _modal(dropped[window]), tolerance):
            n += 1
    return n


def clean_cut(im: Image.Image, box: tuple, side: str, reach: int, tolerance: int = 12) -> int:
    """Where to put the `side` edge of `box` so it cuts the fewest glyphs in two.

    Every edge from where it is to `reach` lines inward is scored by `_straddles`; the least wins,
    and a tie goes to the smallest move. The current edge is a candidate only when the image holds
    the line beyond it, since a cut is judged by what it drops; at the image's own edge the move is
    at least one line. Returns the new coordinate for that edge.
    """
    px = im.convert("RGB").load()
    left, top, right, bottom = box
    if side == "right":
        edges = range(right if right < im.width else right - 1, max(left + 17, right - reach) - 1, -1)
    elif side == "left":
        edges = range(left if left > 0 else left + 1, min(right - 17, left + reach) + 1)
    elif side == "bottom":
        edges = range(bottom if bottom < im.height else bottom - 1, max(top + 17, bottom - reach) - 1, -1)
    else:
        edges = range(top if top > 0 else top + 1, min(bottom - 17, top + reach) + 1)
    return min((_straddles(px, side, box, e, tolerance), abs(e - box[SIDES.index(side)]), e) for e in edges)[2]


def crop_to_outline(path: Path, out: Path | None = None, tolerance: int = TOLERANCE, sides: tuple = SIDES, clean: tuple = (), reach: int = 24) -> tuple:
    """Crop `path` to its subject's outline, in place unless `out` is given, then move any `clean`
    sides off the glyphs they would slice. Returns the box."""
    if set(sides) & set(clean):
        raise SystemExit(f"outline: {', '.join(s for s in SIDES if s in sides and s in clean)} named as both outline and cut; a --clean side is a cut, so leave it out of --sides. Nothing was written.")
    im = Image.open(path)
    box = list(outline_box(im, tolerance, sides))
    for side in clean:
        box[SIDES.index(side)] = clean_cut(im, tuple(box), side, reach)
    box = tuple(box)
    im.crop(box).save(out or path, dpi=im.info.get("dpi"), icc_profile=im.info.get("icc_profile"))
    print(f"{(out or path).name}: cut to the outline {box}, {box[2] - box[0]}x{box[3] - box[1]} of {im.width}x{im.height}")
    return box


def _usage() -> str:
    """The usage block from the docstring, through to the blank line after it."""
    lines = __doc__.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("python outline.py"))
    return textwrap.dedent("\n".join(takewhile(str.strip, lines[start:])))


def main(argv: list[str]) -> int:
    args, out, tolerance, sides, clean, reach, files = list(argv), None, TOLERANCE, None, (), 24, []
    while args:
        a = args.pop(0)
        if a in ("-h", "--help"):
            print(_usage())
            return 0
        if a == "--out":
            out = Path(args.pop(0))
        elif a == "--sides":
            value = args.pop(0)
            sides = () if value == "none" else tuple(x for x in value.split(",") if x)
            if value != "none" and (not sides or any(x not in SIDES for x in sides)):
                raise SystemExit(f"outline: --sides takes sides from {', '.join(SIDES)}, or none")
        elif a == "--clean":
            clean = tuple(x for x in args.pop(0).split(",") if x)
            if not clean or any(x not in SIDES for x in clean):
                raise SystemExit(f"outline: --clean takes sides from {', '.join(SIDES)}")
        elif a == "--reach":
            reach = int(args.pop(0))
        elif a == "--tolerance":
            tolerance = int(args.pop(0))
        elif a.startswith("-"):
            raise SystemExit(f"outline: unknown option {a}\n{_usage()}")
        else:
            files.append(Path(a))
    if len(files) != 1:
        raise SystemExit(_usage())
    if sides is None:
        sides = tuple(s for s in SIDES if s not in clean)
    crop_to_outline(files[0], out, tolerance, sides, clean, reach)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
