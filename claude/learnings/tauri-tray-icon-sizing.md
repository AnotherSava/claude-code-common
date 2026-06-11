# Tauri tray / menu-bar icon: sizing & dynamic rendering

How to render a **dynamic** tray icon (e.g. a live number badge) crisply on both
Windows and macOS, and the platform constraints that dictate the approach.
Verified by web research + reading the `tray-icon` crate source (Tauri's tray
dependency, v0.21).

## Display size per platform

**Windows notification area:** the icon is shown at `16 logical px × DPI scale`,
i.e. `MulDiv(16, dpi, 96)` = `GetSystemMetrics(SM_CXSMICON)` scaled:

| DPI scale | px |
|-----------|----|
| 100%      | 16 |
| 125%      | 20 |
| 150%      | 24 |
| 200%      | 32 |

Windows picks the **next-larger** size in the HICON and **smooth-downscales** it
(bilinear-ish, not nearest). So handing the OS one oversized bitmap (e.g.
128×128) → soft/blurry tray icon — a documented complaint (tauri #9335). Fix:
render at the native size and hand it over ~1:1, or ship native-size frames.
Full RGBA color is supported (no monochrome rule), though MS design guidance
says to avoid pure red/yellow/green in the *base* icon (reserve for status).

**macOS menu bar (`NSStatusItem`):** the `tray-icon` crate ALWAYS forces the
image to 18pt tall, aspect-preserved — see
`tray-icon/src/platform_impl/macos/mod.rs::set_icon_for_ns_status_item_button`:

```rust
let icon_height: f64 = 18.0;
let icon_width = (width as f64) / (height as f64 / icon_height);
nsimage.setSize(NSSize::new(icon_width, icon_height)); // points, not pixels
```

So the menu-bar icon is **fixed at 18pt** regardless of the pixels you supply;
you cannot make it taller. Useful resolution = `18pt × backing scale` (36px on a
2× Retina display). A larger bitmap is just downsampled by AppKit. The menu bar
working area is ~22pt; items can't exceed it.

## macOS template vs colored icons

- A **template image** (`NSImage.isTemplate = true`, or `set_icon_as_template`)
  is treated as an alpha mask: macOS ignores its color and **auto-tints it**
  black on the light menu bar / white in dark mode, and on highlight. This is
  the Apple-recommended path and handles light/dark for free.
- A **non-template colored image renders full-color but gets ZERO light/dark
  adaptation.** A dark icon or a black outline **vanishes on the dark-mode menu
  bar**. There is no API flag that auto-adapts a colored icon — you must swap
  assets on appearance change or draw a neutral/contrasting backplate yourself.

## Text/number legibility

Both platforms converge on **1–2 characters max** at 16–24px. 3+ digits smear —
cap at two (e.g. show `XX` or `99+` for ≥100).

## Rendering technique that works (this project's `tray_badge.rs`)

1. **Render at the exact OS size**: Windows `round(16 × scale)`, macOS
   `round(18 × scale)`, from the main window's `scale_factor()`. Output an
   `Image` at that size so it displays ~1:1.
2. **Area-downscale the source app icon yourself** (alpha-weighted box filter)
   to that size for the badge background — cleaner than the OS's blur.
3. **Rasterize digits from a bundled font with `fontdue`** (pure-Rust, AA) at
   the native size, not an upscaled bitmap font. At ≥24px a real anti-aliased
   glyph looks far better than a 3× bitmap; below that, AA still reads well.
4. **Size from text-INDEPENDENT references** — the tallest glyph and the widest
   two-character string ("88"/"00"/"XX") — and place on a **fixed baseline**
   derived from a reference figure height. Otherwise sizing each number to its
   own bounding box makes a narrow value ("15") grow taller than a wide one
   ("82"), because the narrow one hits the width limit later.
5. **Use an extra-condensed face** (e.g. Saira ExtraCondensed, Bebas Neue) so
   two digits fill the icon height without being shrunk to fit the width.
   Proportional/mono faces leave 2-digit values ~60% height in a square.
6. **Outline** = a 1px dilation of the glyph coverage drawn in black under the
   colored glyph (contrast on any background — but see the macOS caveat above).
7. Re-render on every state change that affects it (usage poll, config, menu).
   Note: no `WM_DPICHANGED` hook means a live monitor-DPI change won't re-render
   until the next such event.

## Getting fonts to bundle

`curl` static TTFs from `github.com/google/fonts` raw paths. Many families are
now **variable** (`Family%5Bwght%5D.ttf`); fontdue/most rasterizers want a
static instance, so instance one with `fonttools`:

```python
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
f = TTFont("Family-VF.ttf")
instantiateVariableFont(f, {"wght": 500}, inplace=True)
f.save("Family-Medium.ttf")
```

Validate a download is a real TTF/OTF before use (magic bytes
`00 01 00 00` / `OTTO` / `true`); GitHub raw 404s return HTML. Bundle the
font's OFL license alongside it.
