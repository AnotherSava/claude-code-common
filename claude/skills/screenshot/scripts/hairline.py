#!/usr/bin/env python3
"""Stroke a hairline around a captured window that has no edge of its own.

    python hairline.py <png> [<png> ...] [--width N] [--color RRGGBB] [--opaque] [--require] [--check]
                       [--radius N] [--cut SIDES]

A STANDALONE CLI BECAUSE IMAGE PROCESSING HAS TO BE SHARED ACROSS PLATFORMS.
A project that ships on more than one OS captures on each of them, and those
capture scripts are rarely in the same language — PowerShell on Windows, shell
or Python on macOS. A script one of them shells out to is the only place they can
hold ONE implementation. The alternative is the same border written twice,
drifting in width, colour or shape on two frames a README prints side by side.
Call it from the project's capture script rather than copying it in. That path is
the same on every machine these dotfiles are installed on, which is the same
condition under which a capture runs at all — and a copy per project is the drift
this exists to prevent.

WHY A WINDOW MIGHT HAVE NO EDGE. macOS strokes a *decorated* window a light
frame and rounds its corners for free, and Windows draws its own translucent
one, so most captures arrive already bordered and are left alone (`has_own_edge`
below). Three kinds do not: an undecorated window; a decorated window with a dark
theme, which macOS gives no light stroke; and a region crop, which never carries
an edge on its cut sides. Without one, a dark screenshot on a dark page has no
boundary at all — and GitHub renders a README in dark mode, where no stylesheet
can reach.

THE RING IS DERIVED FROM THE IMAGE'S OWN ALPHA, never drawn as a shape. Drawing a
parametric rounded rectangle whose radius is measured off the alpha was tried
twice and is wrong at the corners for one reason: macOS does not round a window
with a circular arc. Its corners are continuous — squircles — so a circle fitted
to them sits inside the curve along part of its sweep and outside it along the
rest, and no radius makes a circle match a shape that is not one. The second
failure was worse than cosmetic: `alpha_composite` takes its output alpha from
the source, so wherever the arc fell outside the real corner it painted NEW
opaque pixels and quietly enlarged the window. Eroding the alpha can do neither —
the ring is a subset of the shape by construction.

THE ERODING ELEMENT IS A DISK, NOT A SQUARE, and the difference is visible. A
square kernel — which is all `ImageFilter.MinFilter` offers — erodes `width`
pixels along the axes but `width * sqrt(2)` along a diagonal, so the border comes
out 41% thicker everywhere the edge is curved. Measured on a real widget: 2.00px
on the flat edges against 2.83px through the corner. It was reported by eye as a
fat corner before anyone measured it, and the ratio being exactly sqrt(2) is the
fingerprint.

IT IS DONE AT 3x AND AVERAGED BACK DOWN, because a disk of radius 2 in whole
pixels is still a coarse circle: eroding at 1x leaves the corner 10% thin
(1.80 against 2.00). At 3x it measures 2.06 against 2.00, a 3% difference that no
longer reads. The downsample is BOX — a plain area average — rather than LANCZOS,
whose overshoot puts a dark halo just inside the border; that was tried and is
visible at 9x.

WHAT IS WRITTEN IS COLOUR AND ONLY COLOUR, for a shaped frame. The original alpha
goes back unchanged, so the silhouette is bit-for-bit what the capture had and
the antialiased edge keeps its own coverage instead of being hardened. This is
framing rather than retouching: it adds the edge the OS would have drawn, and
moves nothing.

A FULLY OPAQUE FRAME IS FRAMED OUTWARD INSTEAD. With no transparent pixel the
silhouette is the whole rectangle, and a ring traced inside it would paint over
the outermost `width` pixels of content — on a region crop, the pixels right at
its cut sides. So the canvas grows by `width` on every side and the ring fills
the new margin: every captured pixel survives, bar the corners `--radius` (below)
clips when asked to round them, and the file comes out 2 x `width` larger in each
dimension. A caller comparing dimensions against the frame it replaces compares
like with like: the new frame with the outgoing frame, or the new raw with the
outgoing raw as committed (`git show HEAD:<path>`) — never the raw in the working
tree, which the capture being compared has already overwritten.

`--radius N` ROUNDS THAT OUTWARD FRAME, for a subject whose corners are circular
arcs — a Swing `RoundRectangle2D` such as an IntelliJ Islands panel (the theme's
`Island.arc` is the diameter: 20 gives 10 logical px, 15 px at 144 dpi), or a CSS
`border-radius`. The content is clipped to a rounded rectangle of radius N at its
own extent, antialiased at 4x, and the ring follows it outside with radius
N + `width`, so the band keeps one thickness through the arc and nothing inside
the clip is covered. `--cut SIDES` (comma-separated from left, top, right,
bottom, as in winframe.py) names the sides that are crop cuts: a corner on a cut
side stays square. It is not for a macOS window, whose corners are not circles
(see above), nor for a Windows window, which winframe.py draws from DWM's model.

`--opaque` IS THE ONE EXCEPTION, AND IT IS FOR A CROP OF A WINDOW WHOSE OWN
BORDER IS TRANSLUCENT and which winframe.py cannot model. A crop of a Windows
window is not one: Add-WindowFrame -Cut redraws its whole frame from DWM's model,
so none of the translucent band survives to be replaced. The measurements below
are of a Windows crop all the same. A translucent band — Windows
draws a 2px one that captures at alpha ~120-150 — leaves a crop with a real
border on its uncut sides and nothing on the cut ones, and the two cannot be
made to match. Writing colour
alone leaves the native sides tinted by whatever is behind the page: measured on
a cropped tab strip, the native two read ~162 on white but fell to 53 against a
46 background on a dark page — invisible — while the stroked two read 189 on both. Hardening the ring's alpha makes one border out of the four
sides at any page colour. It is a per-frame decision and belongs to the capture
script that knows how the frame was taken; the DEFAULT IS OFF, because on a
capture whose alpha is genuine coverage the same step would square off a rounded
corner.

Do not reach for it to fix a border that merely looks wrong on one side. Two
earlier attempts at this frame were: stroking only the cut sides, which is
correct on white and leaves a dark page with two visible edges and two invisible
ones; and stroking all four while preserving alpha, which dilutes the colour to
whatever the native alpha allows and reads as a corner darker than the flats.

`--check` WRITES NOTHING. It prints each file as `has an edge` or `NO EDGE`, by
`has_edge`, and exits 1 when any is bare. It is the audit the docs-relevance
skill runs over every committed frame, and some of those carry a `never` policy,
so looking must not be done by the same call that strokes.

FOR A WINDOWS CAPTURE, PREFER `winframe.py` BESIDE THIS FILE. It does not edit the
frame Windows drew; it draws it again from DWM's own model — corner radius, chord
count, antialiasing, the 40% border and, optionally, the shadow — keeping only the
content inside the clip DWM applies. Everything here works on a captured border,
which is the border mixed with whatever shadow and backdrop lay behind it.

ON macOS, RUN THE COLOUR-PROFILE STEP AFTER THIS, not before. A save through
Pillow keeps an embedded `iCCP` profile — the passthrough at the save hands it
over explicitly — but drops the `sRGB` chunk that `sips --matchTo sRGB` leaves,
along with `eXIf` and `cICP`, because Pillow cannot see those and rebuilds the
file from what it holds. These captures are sRGB, so the tag goes entirely and
the frame lands untagged. `~/.claude/learnings/macos-image-inspection.md` carries
the measured chunk-by-chunk table and the per-profile differences; the rule here
is the ordering, which holds whichever profile is used.
"""
import sys
import textwrap
from itertools import takewhile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

# The grey macOS strokes a window frame with — 0xBD — read off a real macOS window
# frame rather than chosen. Matching it is what lets a bordered
# undecorated window sit beside a decorated one without looking edited.
COLOR = (189, 189, 189)
WIDTH = 2       # pixels of the source, which is already 2x on a Retina capture
SUPERSAMPLE = 3
# Alpha at or above this counts as "in the window" when reducing the capture to a
# silhouette. Below it, a pixel is treated as the outer antialiased fringe.
SILHOUETTE = 128
# The same cut under `--opaque`, where it must sit BELOW the native border's own
# alpha or that border lands outside the silhouette, gets stroked as if it were
# fringe, and the ring is then drawn inside it as well — a 4px edge built out of
# two 2px ones. Windows' two observed border alphas are 119 (the undecorated
# widget, keyed from two exposures) and ~130 (a decorated window), which straddle
# `SILHOUETTE`, so the same constant cannot serve both paths: at 128 exactly the
# alpha-119 frames doubled. Measured across all five Windows frames, every value
# from 32 to 100 gives 2px on all four sides, and the corner is visually identical
# across that range; 64 is the middle of it.
#
# THE CORNER HAS NO SINGLE THICKNESS UNDER `--opaque`, and a figure quoted here
# (2.12px) said otherwise until it was re-measured. Walking the normal to the
# curve at 5-degree steps, the band runs 1.99–3.05px around one quarter arc at
# this cut, 1.99–3.18 at 100 — never below the flats, up to half as much again at
# the worst angle. That is the NEAREST upsample above showing through: the shape
# the disk erodes is a 1x staircase rather than a curve, so the band's width
# depends on where around the arc it is asked for. The default path keeps its
# curve and stays even (2.06 against 2.00, in the 3x note above). It is left as
# it is because the alternative is the speckle `ring_of` documents — a visible
# defect traded for a measurable one that nobody has seen. Do not tune a single
# number back into this comment: a 45-degree pixel count cannot resolve it either
# (two samples spaced sqrt(2) apart fit any thickness from ~1.4 to ~2.8), so a
# claim about this corner needs the normal walk, and it comes out a range.
OPAQUE_SILHOUETTE = 64

# `has_own_edge` tuning. `probe` is how far in to look for the content behind the
# border, `contrast` how different that has to be, `share` what fraction of a
# side's positions must show it, `need` how many of the four sides must agree
# before the frame counts as already bordered. Measured over every committed
# frame in the sibling repos: a bordered side reads a share of 0.85 or more; a
# bare side mostly reads near 0, but up to 1.0 where a panel edge or a page margin
# runs within `probe` of it, and a crop of editor text reaches 0.50-0.61. So SHARE
# only discounts sparse content like text, and NEED is what stops one or two such
# bare sides from passing a frame as bordered.
PROBE, CONTRAST, SHARE, NEED = 5, 20, 0.7, 3


def _side_share(positions, at, limit: int, probe: int, contrast: int) -> float:
    """The fraction of `positions` along one side whose outermost opaque pixel contrasts with the one `probe` in.

    `at(pos, k)` is the pixel `k` in from the edge at `pos`; the walk stops at
    `limit`, the side's midpoint.
    """
    hits = valid = 0
    for pos in positions:
        first = next((k for k in range(limit) if at(pos, k)[3] >= OPAQUE_SILHOUETTE), None)
        if first is None or first + probe >= limit:
            continue
        valid += 1
        a, b = at(pos, first), at(pos, first + probe)
        hits += max(abs(a[c] - b[c]) for c in range(3)) > contrast
    return hits / valid if valid else 0.0


def has_own_edge(im: Image.Image, probe: int = PROBE, contrast: int = CONTRAST, share: float = SHARE, need: int = NEED) -> bool:
    """Whether the capture already carries a border on its own.

    ASKED OF ALL FOUR EDGES, because asking one is how this went wrong. The
    intensity window's top row is (73, 73, 75) — the title bar's own highlight —
    while its other three sides are the bare chart background, so a top-edge
    probe called it bordered when three quarters of it had no edge at all. A
    window either has a frame all the way round or it has none.

    The comparison is the outermost pixel at `OPAQUE_SILHOUETTE` alpha or more
    against one `probe` pixels further in. The floor is that low because Windows
    draws its border translucent — measured (101, 101, 101) at alpha 119 — and a
    test that only looked above alpha 200 skipped straight past it and reported
    plainly bordered frames as bare; that mistake reached two committed files. It
    is not zero because a keyed frame's antialiased fringe, alpha ~18, lies
    outside a traced hairline, and comparing the fringe with the ring behind it
    reads as bare. The walk runs to the side's midpoint, so a frame with a
    transparent margin wider than the probe still reaches its edge.

    EACH SIDE IS JUDGED ALONG ITS MIDDLE HALF, not at one point. A border is a
    line that differs from the content behind it nearly everywhere; text differs
    from its background only where a glyph falls. One probe per side called a bare
    867x222 crop of editor text bordered, because three of its four midpoints
    landed on glyphs five pixels in — and the same crop one column wider missed
    them. The corners are left out, where a rounded shape's first opaque pixel is
    its arc rather than its edge.
    """
    w, h = im.size
    px = im.convert("RGBA").load()
    xs, ys = range(w // 4, w - w // 4), range(h // 4, h - h // 4)
    shares = [
        _side_share(xs, lambda x, k: px[x, k], h // 2, probe, contrast),
        _side_share(xs, lambda x, k: px[x, h - 1 - k], h // 2, probe, contrast),
        _side_share(ys, lambda y, k: px[k, y], w // 2, probe, contrast),
        _side_share(ys, lambda y, k: px[w - 1 - k, y], w // 2, probe, contrast),
    ]
    return sum(s >= share for s in shares) >= need


def _shift(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    """`mask` moved, with everything outside the canvas transparent.

    Pasting onto a zero-filled canvas rather than `ImageChops.offset`, which
    wraps: a wrapped edge would erode against the opposite side of the window.
    It also makes the outside genuinely transparent, which is what lets the
    erosion bite on a straight edge that runs to the image boundary — Pillow's
    own rank filters replicate there instead, and a version built on those drew
    the corners only while reporting success.
    """
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (dx, dy))
    return out


def _erode_disk(mask: Image.Image, radius: int) -> Image.Image:
    """`mask` eroded by a disk — the minimum over every offset within `radius`."""
    offsets = [(dx, dy) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1) if dx * dx + dy * dy <= radius * radius]
    out = mask
    for dx, dy in offsets:
        out = ImageChops.darker(out, _shift(mask, dx, dy))
    return out


def ring_of(alpha: Image.Image, width: int = WIDTH, supersample: int = SUPERSAMPLE, opaque: bool = False) -> Image.Image:
    """The band of `width` pixels just inside the shape's own boundary.

    THE RESULT IS NORMALISED BY THE SHAPE'S OWN COVERAGE, which is what stops the
    border going patchy along a curve. Ask what fraction of a pixel the band
    covers and a pixel that is only 27% inside the window can never answer more
    than 0.27, so compositing it paints 27% border over 73% window content — a
    diluted, darker pixel. Ask instead what fraction of the pixel's IN-WINDOW
    area is band, and the answer there is 1.0: every scrap of window in that
    pixel is within `width` of the edge. The border then keeps its full colour
    and the softness lives in the alpha, which is exactly what macOS's own frames
    show — measured on a decorated window's corner, grey 189 at alpha 243, not a
    blend of grey and content.

    Without it the antialiased pixels along a corner carry a muddied colour, and
    the arc reads thinner than the straight runs even though it measures the same
    perpendicular width. A straight edge is unaffected: its pixels are fully
    inside the window, so the normalisation divides by one.

    THE EROSION RUNS ON THE SILHOUETTE, NOT ON THE ALPHA'S GREY LEVELS, and that
    distinction is what keeps the band `width` wide on a capture that ALREADY has
    a border. Eroding the alpha itself treats every change in coverage as an edge,
    so a window whose own frame is a translucent plateau — Windows draws one two
    pixels deep at alpha 142 — gets that plateau propagated inward as well, and
    the band comes out twice as wide there while staying correct on the sides
    without one. Measured on a cropped tab strip: four pixels along the top and
    left, two along the cut right and bottom, from one call. Thresholding first
    makes the shape binary, so only the true outer boundary counts.

    THE OUTER ANTIALIASED FRINGE IS ADDED BACK, because thresholding drops it and
    it is exactly where the colour matters most. A pixel below the threshold is
    barely in the window at all, which means every scrap of window in it is
    within `width` of the edge — so it is wholly band, and takes the border
    colour outright rather than the fraction the threshold would have left it.

    UNDER `opaque` THE UPSAMPLE IS NEAREST RATHER THAN BILINEAR, because the
    threshold then has a plateau to land on. Interpolating first is the better
    choice when the alpha is genuine coverage: it puts the silhouette boundary
    sub-pixel-accurately between two samples. But a translucent border is a FLAT
    run at one value — Windows draws one at alpha ~130 — and `SILHOUETTE` is 128,
    so the cut falls inside the run: interpolation then drags neighbouring samples
    across the threshold and the band comes out with a staircase of half-strength
    pixels through the rounded corner, which reads as speckle. Thresholding at 1x
    and enlarging blockily removes it, and costs nothing the supersample was for —
    the 3x exists so the eroding disk is round, not so the shape is finer.
    """
    cut = OPAQUE_SILHOUETTE if opaque else SILHOUETTE
    if opaque:
        big = alpha.point(lambda v: 255 if v >= cut else 0).resize((alpha.width * supersample, alpha.height * supersample), Image.NEAREST)
    else:
        big = alpha.resize((alpha.width * supersample, alpha.height * supersample), Image.BILINEAR).point(lambda v: 255 if v >= cut else 0)
    band = ImageChops.subtract(big, _erode_disk(big, max(1, round(width * supersample))))
    ring = band.resize(alpha.size, Image.BOX)
    rb, ab = ring.tobytes(), alpha.tobytes()
    return Image.frombytes("L", ring.size, bytes(
        0 if a == 0 else (255 if a < cut else min(255, r * 255 // a)) for r, a in zip(rb, ab)))


def carries_ring(im: Image.Image, color=COLOR, width: int = WIDTH, tolerance: int = 2) -> bool:
    """Whether the outermost `width` pixels along every side's straight run are `color`, fully opaque.

    That band is what the outward frame below adds, and `has_own_edge` cannot be
    trusted to see it: it compares the ring with the content `PROBE` pixels in, so
    content within `CONTRAST` of the ring colour — mid-light grey UI — or a ring
    wider than the probe reads as bare. Every re-run would then grow the frame by
    another ring. The tolerance absorbs an sRGB re-tag after the stroke.
    """
    w, h = im.size
    if w <= 2 * width or h <= 2 * width:
        return False
    rgba = im.convert("RGBA")
    # The straight runs only: a ring drawn with `--radius` leaves its corners
    # transparent, and the arcs themselves are antialiased, so reading the band into
    # the corners would call a rounded frame bare and ring it again on every run.
    # Skipping all but the middle of the shorter sides clears any radius short of a
    # full pill; the longer sides are still read along their whole straight run.
    m = max(0, min(w, h) // 2 - 1)
    for box in ((m, 0, w - m, width), (m, h - width, w - m, h), (0, m, width, h - m), (w - width, m, w, h - m)):
        bands = rgba.crop(box).getextrema()
        if bands[3][0] < 255 or any(lo < c - tolerance or hi > c + tolerance for (lo, hi), c in zip(bands[:3], color)):
            return False
    return True


def has_edge(im: Image.Image, color=COLOR) -> bool:
    """Whether the frame is bordered already, by its own capture or by a ring in `color`.

    The ring is asked about its outermost pixel only, which is where the page meets
    the frame: that recognises this script's outward band at any `--width`, and the
    1 px ring `winframe.py` draws below 144 DPI.
    """
    return has_own_edge(im) or carries_ring(im, color, 1)


def _assert_bordered(im: Image.Image, path: Path, color, phrase: str) -> None:
    """Refuse unless all four edge midpoints carry `color`. Never writes."""
    px = im.convert("RGBA").load()
    x, y = im.width // 2, im.height // 2
    sides = {"top": px[x, 0], "bottom": px[x, im.height - 1], "left": px[0, y], "right": px[im.width - 1, y]}
    missed = [s for s, p in sides.items() if max(abs(p[i] - color[i]) for i in range(3)) > 40]
    if missed:
        raise SystemExit(f"hairline: {path.name} {phrase} the {', '.join(missed)} edge(s) — { {s: sides[s][:3] for s in missed} } rather than {tuple(color)}. Nothing was written.")


SIDES = ("left", "top", "right", "bottom")


def _rounded_mask(size: tuple, box: tuple, radius: float, corners: tuple, ss: int = 4) -> Image.Image:
    """Coverage of a rounded rectangle, drawn at `ss`x and averaged down so its arcs are antialiased."""
    x0, y0, x1, y1 = box
    big = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle((x0 * ss, y0 * ss, x1 * ss - 1, y1 * ss - 1), radius=radius * ss, fill=255, corners=corners)
    return big.resize(size, Image.BOX)


def _round_outward(framed: Image.Image, color, width: int, radius: int, cut: tuple) -> Image.Image:
    """Give an outward-framed rectangle the rounded corners its subject had.

    `framed` is the capture pasted inset by `width` on a canvas of the ring's
    colour. The content is clipped to a rounded rectangle of `radius` at its own
    extent, and the ring follows it outside with radius `radius + width`, so the
    band keeps one thickness through the arc. A corner on a `cut` side stays
    square, as a crop's cut has no corner to round.
    """
    w, h = framed.size
    corners = tuple(not ({a, b} & set(cut)) for a, b in (("top", "left"), ("top", "right"), ("bottom", "right"), ("bottom", "left")))
    outer = _rounded_mask((w, h), (0, 0, w, h), radius + width, corners)
    inner = _rounded_mask((w, h), (width, width, w - width, h - width), radius, corners)
    out = Image.composite(framed, Image.new("RGBA", (w, h), (*color, 255)), inner)
    out.putalpha(outer)
    return out


def add_hairline(path: Path, color=COLOR, width: int = WIDTH, opaque: bool = False, require: bool = False, radius: int = 0, cut: tuple = ()) -> bool:
    """Stroke `path` in place. Returns whether it was changed.

    `opaque` says the frame's own border is a TRANSLUCENT BAND to be replaced
    rather than an edge to be kept — see the module docstring for when that is
    true and what it changes. `radius` and `cut` apply to a fully opaque frame,
    which is framed outward: see the module docstring.
    """
    src = Image.open(path)
    # A single-frame PNG only: the save below writes PNG under whatever name it is
    # given, which turns a JPEG into a PNG with a .jpg name, and `convert` keeps only
    # the first frame of an animated GIF.
    if src.format != "PNG" or getattr(src, "n_frames", 1) > 1:
        raise SystemExit(f"hairline: {path.name} is not a single-frame PNG. Nothing was written.")
    im = src.convert("RGBA")
    # `--opaque` overrides the gate rather than consulting it. The gate asks "does
    # this frame already have a border", and under `--opaque` the answer is YES and
    # is the reason for the call: that native border is translucent, so it reads as
    # a different shade on a light page than on a dark one and cannot match the
    # frames beside it. Consulting the gate here refuses exactly the frames the flag
    # exists for.
    outward = not opaque and im.getchannel("A").getextrema()[0] == 255
    # This script's own rounded ring leaves the corners transparent, so a re-run with the same
    # `--radius` meets a shaped frame; it is recognised by the ring on its straight runs and
    # skipped below, rather than refused here.
    if radius and not outward and not carries_ring(im, color, width):
        raise SystemExit(f"hairline: --radius rounds a fully opaque frame, and {path.name} already has a shape of its own. Nothing was written.")
    # An explicit `--radius` is a request to round this frame, which a native edge
    # does not satisfy: a rounded subject cut to its outline often carries its own
    # border, and skipping on it would ship the corners square with the backdrop in
    # them. So under `--radius` that border is kept and the ring goes outside it, and
    # only this script's own ring, from an earlier run, is a reason to stop.
    if not opaque and (carries_ring(im, color, width) if radius else has_edge(im, color)):
        # `require` is the caller saying "this frame MUST end up bordered". Skipping
        # is then only acceptable if the edge already there is the one we would have
        # drawn, so it is checked rather than assumed. Without this, a `has_own_edge`
        # FALSE POSITIVE is silent and indistinguishable from success: the gate reads
        # contrast a few pixels in, and on a frame whose content runs to the edge — a
        # cropped tab strip dense with glyphs — the glyphs along a side can supply
        # contrast that is not a border. Miscount one bare side of two and the count
        # reaches three, this returns False, and the capture script sees exit 0 and
        # ships an unbordered frame with nothing reporting it. That is the same shape
        # as the defect this module's own docstring records: a check that passes
        # without the thing it checks for having happened.
        if require:
            _assert_bordered(im, path, color, "was left alone because it looked bordered, but")
        print(f"{path.name}: already has an edge, so no hairline was added")
        return False

    alpha = im.getchannel("A")
    # A FULLY OPAQUE FRAME IS A RECTANGLE, AND IT IS FRAMED OUTWARD. The canvas grows
    # by `width` on every side and the ring fills the new margin, so every pixel the
    # capture had survives, bar the corners `radius` clips. The ring traced below sits INSIDE the silhouette, which
    # on a rectangle means painting over the outermost `width` pixels of content —
    # on a region crop those are the pixels right at its cut sides, text included.
    # A shape with transparent corners keeps the inward ring: its edge is already
    # antialiased coverage, and a margin grown around it would be a square box
    # around a rounded window. `outward` is decided above, before the skip gate.
    if outward:
        out = Image.new("RGBA", (im.width + 2 * width, im.height + 2 * width), (*color, 255))
        out.paste(im, (width, width))
        if radius:
            out = _round_outward(out, color, width, radius, cut)
    else:
        ring = ring_of(alpha, width, opaque=opaque)
        solid = Image.new("RGB", im.size, tuple(color))
        out = Image.composite(solid, im.convert("RGB"), ring).convert("RGBA")
        if opaque:
            # Where the ring is solid the band is entirely border, so its alpha is the
            # OS's translucency and nothing of the window shows through it — take it to
            # 255 rather than letting the page behind tint our own frame. The ring is
            # solid on the outer fringe too, because `ring_of` counts every fringe pixel
            # as wholly band, so the fringe is hardened with it and a rounded corner
            # comes out stepped: measured on a raw Windows capture, a corner ramping
            # 38 -> 121 -> 217 -> 244 came out 255 throughout.
            out.putalpha(Image.composite(Image.new("L", im.size, 255), alpha, ring.point(lambda v: 255 if v >= 250 else 0)))
        else:
            out.putalpha(alpha)

    # Assert the border is actually THERE, on all four sides, before saving. An
    # earlier version returned success having drawn it on the corners only, and
    # the check meant to catch that compared alpha before and after — which a
    # border that was never drawn passes perfectly. A check that can pass without
    # the thing it checks for having happened is worse than no check.
    _assert_bordered(out, path, color, "came out bare on")

    # Carry the colour profile and the pixel density across. Pillow reads both into
    # `info` and writes them back only when handed over explicitly, and every
    # operation above builds a NEW image, so a plain save silently drops them —
    # leaving an untagged PNG that everything downstream has to guess about. The
    # guess matters for the profile because the documentation gate identifies a
    # macOS frame by the saturation of its window chrome, and those numbers only
    # mean what it assumes if the file is sRGB; it matters for the density because
    # winframe.py sizes a Windows frame from the DPI the capture recorded.
    out.save(path, icc_profile=im.info.get("icc_profile"), dpi=im.info.get("dpi"))
    how = f"added outside, {im.width}x{im.height} -> {out.width}x{out.height}" if outward else "traced from the alpha"
    if outward and radius:
        how += f", corners rounded to {radius}px" + (f" except on the cut {', '.join(cut)} side(s)" if cut else "")
    print(f"{path.name}: hairline #{color[0]:02x}{color[1]:02x}{color[2]:02x}, {width}px, {how}, all four edges{', replacing a translucent border' if opaque else ''}")
    return True


def _usage() -> str:
    """The usage block from the docstring.

    Found by prefix rather than by line number, which is how this broke: the index
    was 6 and printed "capture scripts are rarely in the same language", a sentence
    from the middle of a paragraph, as the usage message. Any edit to the prose above
    the usage line moves it. Read through to the blank line after it, because the
    usage runs onto a continuation line.
    """
    lines = __doc__.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("python hairline.py"))
    return textwrap.dedent("\n".join(takewhile(str.strip, lines[start:])))


def main(argv: list[str]) -> int:
    args, width, color, opaque, require, check, radius, cut, files = list(argv), WIDTH, COLOR, False, False, False, 0, (), []
    while args:
        a = args.pop(0)
        if a in ("-h", "--help"):
            print(_usage())
            return 0
        if a == "--width":
            width = int(args.pop(0))
        elif a == "--radius":
            radius = int(args.pop(0))
        elif a == "--cut":
            cut = tuple(s for s in args.pop(0).split(",") if s)
            if any(s not in SIDES for s in cut):
                raise SystemExit(f"hairline: --cut takes sides from {', '.join(SIDES)}")
        elif a == "--opaque":
            opaque = True
        elif a == "--require":
            require = True
        elif a == "--check":
            check = True
        elif a == "--color":
            hexv = args.pop(0).lstrip("#")
            if len(hexv) != 6:
                raise SystemExit("hairline: --color wants RRGGBB")
            color = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        elif a.startswith("-"):
            raise SystemExit(f"hairline: unknown option {a}\n{_usage()}")
        else:
            files.append(Path(a))
    if not files:
        raise SystemExit(_usage())
    if radius and opaque:
        raise SystemExit("hairline: --radius rounds a fully opaque frame framed outward, and --opaque replaces a translucent border traced inward; pass one or the other. Nothing was written.")
    if check:
        bare = [f for f in files if not has_edge(Image.open(f).convert("RGBA"), color)]
        for f in files:
            print(f"{f}: {'NO EDGE' if f in bare else 'has an edge'}")
        return 1 if bare else 0
    for f in files:
        add_hairline(f, color=color, width=width, opaque=opaque, require=require, radius=radius, cut=cut)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
