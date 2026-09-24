#!/usr/bin/env python3
"""Draw the Windows 11 window frame onto a capture, the way DWM draws it.

    python winframe.py <png> [<png> ...] [--dpi N] [--kind window|menu] [--shadow none|STYLE]
                       [--ring RRGGBB:ALPHA] [--cut SIDES] [--out PATH]

A capture of a Windows window already carries DWM's frame, but not one that can be
kept: its border is translucent, so it arrives mixed with whatever shadow and
backdrop lay behind it, and every attempt to clean it up after the fact — tint it,
lift it, copy another window's — worked on pixels that were never the border
alone. This draws the frame from the model instead, and keeps only the capture's
content, inside the clip DWM itself applies.

THE MODEL, measured against two-exposure captures at 144 DPI and against the
uDWM.dll 10.0.26100 disassembly (constants cited where they are used):

- The frame rect is the capture: window-shot crops to DWMWA_EXTENDED_FRAME_BOUNDS.
- Corners are circles of radius 8 DIP for a window (DWMWCP_ROUND) and 4 DIP for a
  menu (DWMWCP_ROUNDSMALL), as floats: 12 and 6 px at 144 DPI. Direct2D flattens
  each quarter circle into K equal-angle chords, and the chords are what shows:
  K = 8 on a window's outline, 4 on its content clip; 4 and 2 on a menu's. A true
  circle is 0.19 px off on the clip. Those counts are measured at 144 DPI only;
  elsewhere K is taken as the radius in DIPs, which is one of three rules that
  agree at 144 and has not been checked at any other scale.
- Edges are antialiased as coverage = clamp(0.5 - d, 0, 1), d the signed distance
  from the pixel centre to the polygon — not area coverage, which measured four
  times worse — and straight edges on whole pixels come out hard.
- The border is t = floor((dpi + 48) / 96) px thick: 1 at 96 DPI, 2 at 144. The
  content is clipped to the frame inset by t, radius R - t, and the border ring is
  the outline minus a hole inset by t + 1, radius R - t - 1, so it runs one pixel
  under the content's antialiased edge and no seam shows.
- A window's border is RGB(117, 117, 117) at alpha 0.40 on every side, in light and
  dark frames alike (uDWM OVERLAPPED_BORDER_COLOR; WinUI SurfaceStrokeColorDefault,
  #66757575). A light menu's is opaque (229, 229, 229). `--ring` overrides it.
- THE SHADING a captured border shows — lighter along the top, darker along the
  bottom — is not the border. It is the drop shadow showing through a uniform 40%
  border. With `--shadow none` the band is uniform; with a style number the shadow
  is rendered as DWM builds it (two Gaussians, sigma = radius / 3, on a square
  source stretched as a nine-grid) and cropped at the frame, so the band carries the
  grading a real capture has. Style 2 is an active light-frame window, 3 an active
  dark-frame one (DWMWA_USE_IMMERSIVE_DARK_MODE), 4 and 5 their inactive forms, 1
  a menu. Pick it from the window, not the system theme.

The scale comes from `--dpi`, or else from the PNG's own resolution (its pHYs
chunk), which the capture should set to the window's DPI: the frame's radius and
thickness are both functions of it, and a capture carries no other record of the
display it was taken on. A PNG with neither is refused rather than guessed at.

`--cut` names sides that are crop cuts rather than the window's own edges — a
tab strip cut out of a terminal window. Those sides get the border drawn straight
along them, and the corners they meet are square.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

# style -> (radius1, radius2 at 96 DPI, alpha1, alpha2); uDWM GetShadowParameters.
SHADOW = {1: (16, 0, 0.14, 0), 2: (64, 128 / 3, 0.28, 0.22), 3: (64, 128 / 3, 0.56, 0.55),
          4: (64, 64 / 3, 0.19, 0.15), 5: (64, 64 / 3, 0.37, 0.37)}
WINDOW_RING = ((117, 117, 117), 0.40)
MENU_RING = ((229, 229, 229), 1.0)
SIDES = ("left", "top", "right", "bottom")


def _polygon(l, t, r, b, radii, k):
    """Vertices of a rounded rectangle whose quarter circles are flattened into k chords each.

    `radii` is (top-left, top-right, bottom-right, bottom-left); a zero radius is a
    square corner. Clockwise in image coordinates, starting at the top-left arc.
    """
    tl, tr, br, bl = radii
    pts = []
    for (cx, cy, rad, a0) in ((l + tl, t + tl, tl, np.pi), (r - tr, t + tr, tr, 1.5 * np.pi),
                              (r - br, b - br, br, 0.0), (l + bl, b - bl, bl, 0.5 * np.pi)):
        if rad <= 0:
            pts.append((cx, cy))
            continue
        for i in range(k + 1):
            a = a0 + (np.pi / 2) * i / k
            pts.append((cx + rad * np.cos(a), cy + rad * np.sin(a)))
    return pts


def _coverage(shape, pts):
    """clamp(0.5 - d, 0, 1) for d the signed distance to a convex polygon, at every pixel centre.

    For a convex polygon the signed distance inside is the largest distance to
    any edge's line, and outside it is the same except next to a vertex, where
    it reads short by at most the exterior angle's sag — under 0.02 px for the
    11.25-degree turns of an 8-chord arc, which a 1 px ramp cannot show.
    """
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w]
    px, py = xs + 0.5, ys + 0.5
    d = np.full(shape, -np.inf)
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        ln = np.hypot(ex, ey)
        if ln < 1e-9:
            continue
        # Outward normal: the vertices run clockwise on screen (y grows downward),
        # so a top edge heading right has its outside above it.
        nx, ny = ey / ln, -ex / ln
        d = np.maximum(d, (px - x0) * nx + (py - y0) * ny)
    return np.clip(0.5 - d, 0.0, 1.0)


def _rrect_supersampled(shape, l, t, r, b, rad, ss=8):
    """Area coverage of a circular rounded rectangle. Used only as the shadow's source shape, which a blur makes indifferent to the edge model."""
    h, w = shape
    ys = (np.arange(h * ss) + 0.5) / ss
    xs = (np.arange(w * ss) + 0.5) / ss
    X, Y = np.meshgrid(xs, ys)
    cx = np.clip(X, l + rad, r - rad)
    cy = np.clip(Y, t + rad, b - rad)
    inside = ((X - cx) ** 2 + (Y - cy) ** 2 <= rad * rad) & (X >= l) & (X <= r) & (Y >= t) & (Y <= b)
    return inside.reshape(h, ss, w, ss).mean(axis=(1, 3))


def _shadow(w, h, scale, style, radius):
    """DWM's shadow alpha over the frame rect itself (the part a capture keeps), per uDWM CreateBorderSurface.

    The shadow is drawn once on a square source and stretched onto the window as a
    nine-grid. The stretch is not a detail: the ramp down a window's sides comes
    from a 68 px source strip spread over the whole height, and blurring a full-size
    rectangle gives a different profile.
    """
    r1d, r2d, a1, a2 = SHADOW[style]
    r1, r2 = r1d * scale, r2d * scale
    m = max(2 * (radius + 2), r1)
    s = int(round(2 * r1 + m))
    body = _rrect_supersampled((s, s), r1, r1, r1 + m, r1 + m, radius)
    sh = gaussian_filter(body, r1 / 3, mode="constant") * a1
    if r2:
        yy, xx = np.mgrid[0:s, 0:s].astype(float)
        moved = map_coordinates(gaussian_filter(body, r2 / 3, mode="constant"), [yy + r1 / 2 - 2 * scale, xx], order=1, mode="constant")
        sh2 = moved * a2
        sh = sh2 + sh * (1 - sh2)
    lo_x, lo_y, hi_x, hi_y = r1 + radius + 2, r1 / 2 + radius + 2, r1 + radius + 2, 1.5 * r1 + radius + 2
    dw, dh = int(round(w + 2 * r1)), int(round(h + 2 * r1))

    def axis(n_dst, lo, hi):
        d = np.arange(n_dst) + 0.5
        mid_src, mid_dst = s - lo - hi, n_dst - lo - hi
        return np.where(d < lo, d, np.where(d >= n_dst - hi, d - (n_dst - s), lo + (d - lo) * mid_src / mid_dst)) - 0.5

    ox, oy = int(round(r1)), int(round(r1 / 2))
    sx, sy = axis(dw, lo_x, hi_x)[ox:ox + w], axis(dh, lo_y, hi_y)[oy:oy + h]
    Y, X = np.meshgrid(sy, sx, indexing="ij")
    return map_coordinates(sh, [Y, X], order=1)


def draw_frame(img: Image.Image, dpi: int, kind: str = "window", shadow=None, ring=None, cut=()) -> Image.Image:
    """`img` with its frame drawn by the model: content kept inside DWM's clip, the ring and outside drawn."""
    scale = dpi / 96
    rgba = np.asarray(img.convert("RGBA")).astype(float)
    h, w = rgba.shape[:2]
    radius = (8.0 if kind == "window" else 4.0) * scale
    k_outer = 8 if kind == "window" else 4
    k_clip = max(1, k_outer // 2)
    t = (dpi + 48) // 96
    colour, alpha = ring or (WINDOW_RING if kind == "window" else MENU_RING)

    # Cut sides lie at the image edge like the others, but are straight and their
    # corners square: a crop has no rounded corner where it was cut.
    def radii(rad):
        tl = 0 if ("left" in cut or "top" in cut) else rad
        tr = 0 if ("right" in cut or "top" in cut) else rad
        br = 0 if ("right" in cut or "bottom" in cut) else rad
        bl = 0 if ("left" in cut or "bottom" in cut) else rad
        return (tl, tr, br, bl)

    co = _coverage((h, w), _polygon(0, 0, w, h, radii(radius), k_outer))
    clip = _coverage((h, w), _polygon(t, t, w - t, h - t, radii(radius - t), k_clip))
    ring_mask = 1 - _coverage((h, w), _polygon(t + 1, t + 1, w - t - 1, h - t - 1, radii(radius - t - 1), k_clip))
    shade = _shadow(w, h, scale, shadow, radius) if shadow else np.zeros((h, w))

    # The frame layer, premultiplied: the ring over the shadow, both masked to the ring.
    frame_a = (alpha * co + shade * (1 - alpha * co)) * ring_mask
    frame_p = np.stack([c * alpha * co * ring_mask for c in colour], axis=-1)

    # Content wherever the clip covers the pixel, taken from the nearest pixel the
    # clip covers fully: at the clip's own edge the capture's pixels are already
    # mixed with DWM's ring and would bring the old frame back.
    full = clip >= 1.0
    _, (iy, ix) = distance_transform_edt(~full, return_indices=True)
    content = rgba[iy, ix, :3]

    out_p = clip[..., None] * content + (1 - clip[..., None]) * frame_p
    out_a = clip + (1 - clip) * frame_a
    colour_out = np.where(out_a[..., None] > 0, out_p / np.maximum(out_a[..., None], 1e-9), 0)
    out = np.dstack([np.clip(np.round(colour_out), 0, 255), np.clip(np.round(out_a * 255), 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main(argv: list[str]) -> int:
    args = list(argv)
    dpi, kind, shadow, ring, cut, out, files = None, "window", None, None, (), None, []
    while args:
        a = args.pop(0)
        if a == "--dpi":
            dpi = int(args.pop(0))
        elif a == "--kind":
            kind = args.pop(0)
            if kind not in ("window", "menu"):
                raise SystemExit("winframe: --kind is window or menu")
        elif a == "--shadow":
            v = args.pop(0)
            shadow = None if v == "none" else int(v)
            if shadow is not None and shadow not in SHADOW:
                raise SystemExit(f"winframe: --shadow is none or one of {sorted(SHADOW)}")
        elif a == "--ring":
            hexv, _, al = args.pop(0).partition(":")
            hexv = hexv.lstrip("#")
            if len(hexv) != 6 or not al:
                raise SystemExit("winframe: --ring wants RRGGBB:ALPHA, e.g. 757575:0.40")
            ring = (tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4)), float(al))
        elif a == "--cut":
            cut = tuple(s for s in args.pop(0).split(",") if s)
            if any(s not in SIDES for s in cut):
                raise SystemExit(f"winframe: --cut takes sides from {', '.join(SIDES)}")
        elif a == "--out":
            out = Path(args.pop(0))
        else:
            files.append(Path(a))
    if not files:
        raise SystemExit(next(l.strip() for l in __doc__.splitlines() if l.strip().startswith("python winframe.py")))
    if out and len(files) > 1:
        raise SystemExit("winframe: --out takes one input")
    for f in files:
        im = Image.open(f)
        file_dpi = im.info.get("dpi")
        use = dpi or (round(file_dpi[0]) if file_dpi and file_dpi[0] > 1 else None)
        if not use:
            raise SystemExit(f"winframe: {f.name} records no DPI; pass --dpi. Nothing was written.")
        framed = draw_frame(im, use, kind, shadow, ring, cut)
        target = out or f
        framed.save(target, icc_profile=im.info.get("icc_profile"), dpi=(use, use))
        print(f"{target.name}: Windows {kind} frame drawn at {use} DPI, shadow {shadow or 'none'}{', ring ' + str(ring) if ring else ''}{', cut ' + ','.join(cut) if cut else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
