#!/usr/bin/env python3
"""Stroke a hairline around a captured window that has no edge of its own.

    python hairline.py <png> [<png> ...] [--width N] [--color RRGGBB] [--opaque] [--require]

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

`scripts/docborder.swift` next to this file predates it and still has one thing
this does not: given `--radius` it CLIPS the corners transparent, which is how a
region crop gets the rounded corners it never had. Reach for that when the
subject is a crop. For a window capture prefer this, and see the geometry note
below for why its stroke cannot sit on a macOS window's corner.

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

WHAT IS WRITTEN IS COLOUR AND ONLY COLOUR. The original alpha goes back
unchanged, so the silhouette is bit-for-bit what the capture had and the
antialiased edge keeps its own coverage instead of being hardened. This is
framing rather than retouching: it adds the edge the OS would have drawn, and
moves nothing.

`--opaque` IS THE ONE EXCEPTION, AND IT IS FOR A CROP OF A WINDOW WHOSE OWN
BORDER IS TRANSLUCENT. Windows draws one that way — a flat 2px band at alpha
~130 — so a crop of such a window arrives with a real border on its uncut sides
and nothing on the cut ones, and the two cannot be made to match. Writing colour
alone leaves the native sides tinted by whatever is behind the page: measured on
a cropped tab strip, all four sides agreed at ~162 on white while on a dark page
the native two fell to 53 against a 46 background — invisible — and the stroked
two sat at 162. Hardening the ring's alpha makes one border out of the four
sides at any page colour. It is a per-frame decision and belongs to the capture
script that knows how the frame was taken; the DEFAULT IS OFF, because on a
capture whose alpha is genuine coverage the same step would square off a rounded
corner.

Do not reach for it to fix a border that merely looks wrong on one side. Two
earlier attempts at this frame were: stroking only the cut sides, which is
correct on white and leaves a dark page with two visible edges and two invisible
ones; and stroking all four while preserving alpha, which dilutes the colour to
whatever the native alpha allows and reads as a corner darker than the flats.

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
from pathlib import Path

from PIL import Image, ImageChops

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
# border, `contrast` how different that has to be, `need` how many of the four
# sides must agree before the frame counts as already bordered.
PROBE, CONTRAST, NEED = 5, 20, 3


def has_own_edge(im: Image.Image, probe: int = PROBE, contrast: int = CONTRAST, need: int = NEED) -> bool:
    """Whether the capture already carries a border on its own.

    ASKED OF ALL FOUR EDGES, because asking one is how this went wrong. The
    intensity window's top row is (73, 73, 75) — the title bar's own highlight —
    while its other three sides are the bare chart background, so a top-edge
    probe called it bordered when three quarters of it had no edge at all. A
    window either has a frame all the way round or it has none.

    The comparison is the outermost pixel with ANY alpha against one `probe`
    pixels further in. Any alpha, not a threshold: Windows draws its border
    translucent — measured (101, 101, 101) at alpha 119 — and a test that only
    looked above alpha 200 skipped straight past it and reported plainly bordered
    frames as bare. That mistake reached two committed files.
    """
    w, h = im.size
    px = im.convert("RGBA").load()
    x, y = w // 2, h // 2
    walks = [
        [px[x, r] for r in range(min(probe + 4, h))],
        [px[x, h - 1 - r] for r in range(min(probe + 4, h))],
        [px[c, y] for c in range(min(probe + 4, w))],
        [px[w - 1 - c, y] for c in range(min(probe + 4, w))],
    ]
    bordered = 0
    for walk in walks:
        first = next((i for i, p in enumerate(walk) if p[3] > 0), None)
        if first is None or first + probe >= len(walk):
            continue
        a, b = walk[first], walk[first + probe]
        if max(abs(a[i] - b[i]) for i in range(3)) > contrast:
            bordered += 1
    return bordered >= need


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


def _assert_bordered(im: Image.Image, path: Path, color, phrase: str) -> None:
    """Refuse unless all four edge midpoints carry `color`. Never writes."""
    px = im.convert("RGBA").load()
    x, y = im.width // 2, im.height // 2
    sides = {"top": px[x, 0], "bottom": px[x, im.height - 1], "left": px[0, y], "right": px[im.width - 1, y]}
    missed = [s for s, p in sides.items() if max(abs(p[i] - color[i]) for i in range(3)) > 40]
    if missed:
        raise SystemExit(f"hairline: {path.name} {phrase} the {', '.join(missed)} edge(s) — { {s: sides[s][:3] for s in missed} } rather than {tuple(color)}. Nothing was written.")


def add_hairline(path: Path, color=COLOR, width: int = WIDTH, opaque: bool = False, require: bool = False) -> bool:
    """Stroke `path` in place. Returns whether it was changed.

    `opaque` says the frame's own border is a TRANSLUCENT BAND to be replaced
    rather than an edge to be kept — see the module docstring for when that is
    true and what it changes.
    """
    im = Image.open(path).convert("RGBA")
    # `--opaque` overrides the gate rather than consulting it. The gate asks "does
    # this frame already have a border", and under `--opaque` the answer is YES and
    # is the reason for the call: that native border is translucent, so it reads as
    # a different shade on a light page than on a dark one and cannot match the
    # frames beside it. Consulting the gate here refuses exactly the frames the flag
    # exists for.
    if not opaque and has_own_edge(im):
        # `require` is the caller saying "this frame MUST end up bordered". Skipping
        # is then only acceptable if the edge already there is the one we would have
        # drawn, so it is checked rather than assumed. Without this, a `has_own_edge`
        # FALSE POSITIVE is silent and indistinguishable from success: the gate probes
        # the midpoint of each side, and on a frame whose content runs to the edge — a
        # cropped tab strip full of glyphs — a midpoint landing on a glyph edge shows
        # contrast that is not a border. Miscount one bare side of two and the count
        # reaches three, this returns False, and the capture script sees exit 0 and
        # ships an unbordered frame with nothing reporting it. That is the same shape
        # as the defect this module's own docstring records: a check that passes
        # without the thing it checks for having happened.
        if require:
            _assert_bordered(im, path, color, "was left alone because it looked bordered, but")
        print(f"{path.name}: already has an edge of its own, so no hairline was added")
        return False

    alpha = im.getchannel("A")
    ring = ring_of(alpha, width, opaque=opaque)
    solid = Image.new("RGB", im.size, tuple(color))
    out = Image.composite(solid, im.convert("RGB"), ring).convert("RGBA")
    if opaque:
        # Where the ring is solid the band is entirely border, so its alpha is the
        # OS's translucency and nothing of the window shows through it — take it to
        # 255 rather than letting the page behind tint our own frame. Where the ring
        # is partial the alpha really is coverage (the shape's outer fringe), and
        # that is left alone, which is what keeps a rounded corner from squaring off.
        out.putalpha(Image.composite(Image.new("L", im.size, 255), alpha, ring.point(lambda v: 255 if v >= 250 else 0)))
    else:
        out.putalpha(alpha)

    # Assert the border is actually THERE, on all four sides, before saving. An
    # earlier version returned success having drawn it on the corners only, and
    # the check meant to catch that compared alpha before and after — which a
    # border that was never drawn passes perfectly. A check that can pass without
    # the thing it checks for having happened is worse than no check.
    _assert_bordered(out, path, color, "came out bare on")

    # Carry the colour profile across. Pillow reads it into `info` and writes it
    # back only when handed over explicitly, and every operation above builds a
    # NEW image, so a plain save silently drops it — leaving an untagged PNG that
    # everything downstream has to guess about. The guess matters here: the
    # documentation gate identifies a macOS frame by the saturation of its window
    # chrome, and those numbers only mean what it assumes if the file is sRGB.
    out.save(path, icc_profile=im.info.get("icc_profile"))
    print(f"{path.name}: hairline #{color[0]:02x}{color[1]:02x}{color[2]:02x}, {width}px, traced from the alpha, all four edges{', replacing a translucent border' if opaque else ''}")
    return True


def main(argv: list[str]) -> int:
    args, width, color, opaque, require, files = list(argv), WIDTH, COLOR, False, False, []
    while args:
        a = args.pop(0)
        if a == "--width":
            width = int(args.pop(0))
        elif a == "--opaque":
            opaque = True
        elif a == "--require":
            require = True
        elif a == "--color":
            hexv = args.pop(0).lstrip("#")
            if len(hexv) != 6:
                raise SystemExit("hairline: --color wants RRGGBB")
            color = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        else:
            files.append(Path(a))
    if not files:
        # Found by prefix rather than by line number, which is how this broke: the
        # index was 6 and printed "capture scripts are rarely in the same language",
        # a sentence from the middle of a paragraph, as the usage message. Any edit
        # to the prose above the usage line moves it.
        raise SystemExit(next(l.strip() for l in __doc__.splitlines() if l.strip().startswith("python hairline.py")))
    for f in files:
        add_hairline(f, color=color, width=width, opaque=opaque, require=require)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
