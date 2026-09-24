# How Windows 11 draws a window's frame, and why a captured one cannot be cleaned up

A captured Windows 11 frame looks like a border with a gradient: lighter along the top, darker toward the bottom, soft at the corners. It is not one. DWM draws a **uniform, semi-transparent border** and a **drop shadow underneath it**, and the grading is the shadow showing through. Every treatment that works on the captured pixels — tinting them, raising their opacity, copying another window's edge — is working on border-plus-shadow-plus-backdrop and cannot get back to the border alone. Draw the frame again from the model instead, and keep only what lies inside DWM's content clip.

Established on 2026-09-24 from three sources that agree: Microsoft's documentation, the uDWM.dll 10.0.26100 symbols and disassembly (via the Windhawk corner-radius mod and valinet's write-up), and measurement of two-exposure captures at 144 DPI (a white WinForms dialog, a dark decorated window, an undecorated transparent Tauri window, a `TrackPopupMenu` menu). A renderer built from it reproduced those captures to **0.21, 0.25 and 0.05 alpha levels RMS** in the edge band, dialog, dark window and menu respectively.

## The model

With `s = dpi / 96`, a frame rect of `W × H` (`DWMWA_EXTENDED_FRAME_BOUNDS`, whole pixels):

| Parameter | Value | Source |
|---|---|---|
| Corner radius R | 8·s for a window (`DWMWCP_ROUND`), 4·s for a menu (`DWMWCP_ROUNDSMALL`), as floats: 12 and 6 px at 144 DPI | [Geometry guidance](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/geometry) "8px ... 4px"; uDWM `GetRadiusFromCornerStyle` returns 8.0 / 4.0; measured |
| Corner shape | a circle, **flattened by Direct2D into K equal-angle chords**: K = 8 on a window's outline and 4 on its content clip; 4 and 2 on a menu's | measured: a chord polygon fits 3–10× better than any superellipse, which only looked right because it approximates the polygon |
| Antialiasing | coverage = clamp(0.5 − d, 0, 1), d the signed distance from the pixel centre to the polygon | measured: a 1.0 px ramp beats 0.9 and 1.1, and area coverage (supersampling) fits four times worse |
| Border thickness t | floor((dpi + 48) / 96): 1 at 96 and 120 DPI, 2 at 144 | `DWMWA_VISIBLE_FRAME_BORDER_THICKNESS` read live; measured |
| Content clip | the frame inset by t, radius R − t | measured: the band's premultiplied value is the same whatever the content, so content never shows under it |
| Border ring | the outline minus a hole inset by t + 1, radius R − t − 1, so it runs one pixel under the content's antialiased edge and no seam shows | disassembly; measured |
| Window border colour | RGB(117,117,117) at alpha 0.40 on every side, in light and dark frames, active and inactive | uDWM `OVERLAPPED_BORDER_COLOR`; equal to WinUI `SurfaceStrokeColorDefault` #66757575; measured alpha 0.4007 |
| Light menu border | opaque (229,229,229) round a (249,249,249) body | measured on a tray menu |
| Shadow | two black Gaussians (σ = radius / 3) drawn once on a square source and stretched onto the window as a nine-grid; about twice as dark on a dark-mode frame (`DWMWA_USE_IMMERSIVE_DARK_MODE`) | uDWM `GetShadowParameters` / `CreateBorderSurface`; measured to within 1 level |

The numbers that only hold at 144 DPI are the chord counts. At other scales the likeliest rule is K = the radius in DIPs, but that is unverified.

## What this means for a capture

- **The captured band is not the border.** Solved from exposures over black and white, a window's top edge measures alpha ~119, its sides ~128 rising toward the bottom, its bottom ~149 — while its premultiplied value stays flat at 46.8. That signature (flat premultiplied value, varying alpha) is a fixed colour over a varying black layer: the shadow.
- **Keep the content, redraw the rest.** Everything inside the content clip is the app's own pixels; everything outside it is DWM's. So a frame can be redrawn over a capture — or over an old screenshot whose outer 2 px were already overwritten by some earlier border treatment — without re-taking it. Check the clip's own pixels against an earlier capture before trusting that: a treatment whose ring was eroded from a curved alpha can reach one pixel inside the clip near a corner.
- **A frame carries no record of its DPI** unless the capture writes one. `Bitmap.SetResolution(dpi, dpi)` before saving puts it in the PNG's pHYs chunk, and Pillow reads it back as `info["dpi"]`.
- **An app's own `border-radius` fights this on Windows.** See `tauri-windows-native.md`: a CSS radius larger than DWM's leaves a transparent arc inside Windows' border.
- **Maximized and snapped windows have square corners and no rounding**, so a model of a normal window is wrong for them.

The docs-relevance skill's `scripts/winframe.py` implements the model, including `--cut` for crops whose cut sides should run straight with square corners, and `--ring` / `--shadow` to choose the look.
