# Inspecting and rasterizing images on macOS with no image library

A stock macOS box has neither Pillow nor ImageMagick nor ffmpeg. That is usually discovered halfway
through a task, so the fallbacks are worth knowing before reaching for `pip install`.

## What is actually there

| Need | Tool | Command |
|---|---|---|
| Dimensions | `sips` | `sips -g pixelWidth -g pixelHeight in.png` |
| Format conversion | `sips` | `sips -s format png in.webp --out out.png` |
| Resize | `sips` | `sips -Z 240 in.png --out out.png` (fit), `-z H W` (exact) |
| Rasterize SVG | `qlmanage` | `qlmanage -t -s 240 -o /tmp in.svg` → writes `/tmp/in.svg.png` |

`qlmanage` renders through QuickLook, so it handles SVG, PDF and anything else with a thumbnailer —
it is the only SVG rasterizer present by default. It writes `<name>.<ext>.png` into `-o`'s directory
rather than to a path you choose, and it renders the document square at `-s`, so a wide SVG comes
back letterboxed or cropped. Give the SVG its own `width`/`height` and render each piece separately
rather than fighting the thumbnail box.

`sips` crops only from the centre in the shipped version — **`--cropOffset` is not supported** and
fails the whole invocation with a bare exit 13 and a usage message. There is no built-in way to cut
tile (row, col) out of a sprite sheet.

## Judging how an icon reads at its real size

Rendering an icon at 240px tells you nothing about how it survives at 20px. Rasterize large, then
downscale to the real size, then magnify *that* — the second scale-up shows what antialiasing did
rather than what the vector says:

```bash
qlmanage -t -s 240 -o /tmp icon.svg          # /tmp/icon.svg.png
sips -z 20 20 /tmp/icon.svg.png --out /tmp/small.png
sips -Z 240 /tmp/small.png --out /tmp/small-magnified.png
```

Detail that vanishes between step 2 and step 3 — a hairline rule, a 1px inner border — is detail the
user will never see.

## A `.png` URL can return WebP

Content negotiation keys on `Accept`, not on the extension, so `curl -o icons.png <…/icons.png>` can
land a RIFF/WebP file with a `.png` name. Nothing complains until a decoder does. Check the magic
bytes (`head -c 16 file | od -c` — `RIFF…WEBP`), and convert with `sips -s format png` before
anything else touches it. `sips -g pixelWidth` happily reports dimensions for the WebP, so a
successful size read is *not* evidence the file is a PNG.

## Reading pixels with no library

For measurements — a glyph's alpha bounding box inside a sprite cell, say — a PNG decoder in pure
Python is about forty lines and needs only `zlib` and `struct`: parse `IHDR`, concatenate the `IDAT`
chunks, `zlib.decompress`, then undo the five per-scanline filters (None/Sub/Up/Average/Paeth). It is
slow and it only handles the case in front of you, but it answers questions no CLI tool will —
"do these tiles fill their cells or is there padding?" is a five-line loop over the alpha channel
once the rows are unfiltered.

Two cautions. Convert to PNG first (see above), and check the colour type from `IHDR` rather than
assuming RGBA — `sips` conversion gives type 6 (RGBA, 8-bit, non-interlaced), which is the easy case,
but an interlaced or palette image needs different handling. And confirm alpha actually survived the
conversion before trusting a bounding box: sample a corner you expect to be transparent, because a
flattened image measures every tile as "fills its cell".

## Writing a PNG back out

The inverse is shorter than the decoder and useful for cropping a sprite cell into something you can
look at: emit `IHDR`, one `IDAT` of `zlib.compress` over rows each prefixed with a `0` filter byte,
and `IEND`, with a CRC32 over type+data on each chunk. Compositing the crop over a solid background
while writing it is worth doing — transparency renders as white in most viewers, which hides exactly
the padding you were trying to measure.
