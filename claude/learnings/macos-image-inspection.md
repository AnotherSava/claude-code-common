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

## Colour tags: what `sips` writes is not what Pillow can keep

A PNG can carry its colour space two different ways, and **which one `sips` writes depends on the
profile handed to it** — so a rule derived from one `--matchTo` run does not hold for the next.
Measured on one image, tagged three ways and then saved through Pillow:

| tagged by                        | chunks in              | Pillow sees | chunks out    |
|----------------------------------|------------------------|-------------|---------------|
| Pillow `icc_profile=` (P3)       | `IHDR iCCP`            | 536 bytes   | `IHDR iCCP`   |
| `sips --matchTo` **sRGB**        | `IHDR sRGB eXIf`       | **0 bytes** | **`IHDR`**    |
| `sips --matchTo` **Display P3**  | `IHDR iCCP cICP eXIf`  | 536 bytes   | `IHDR iCCP`   |

Matching to sRGB writes a **`sRGB` chunk** — a one-byte rendering intent — because PNG has a
dedicated chunk for that case, and `sips` reports success either way. Pillow cannot see that chunk
at all (`Image.open(p).info["icc_profile"]` is empty) and cannot write one back, so the tag is gone
after any save. Matching to any other profile embeds an ordinary `iCCP`, which Pillow reads and the
passthrough below carries through byte-identical.

The **`eXIf` block dies in both `sips` cases, and so does `cICP`**, whether or not the profile
survives — Pillow rebuilds the file from the pixels it holds and carries over only what it was
handed.

So on macOS, run the `sips` colour step **after** anything that saves through Pillow, never before.
That is not only about the sRGB row: the other rows keep their profile but still lose `eXIf`.

The `icc_profile=` passthrough is for the other kind of tag and does hold:

```python
im = Image.open(p)
# ... every operation builds a NEW image, so info["icc_profile"] must be handed over explicitly
out.save(p, icc_profile=im.info.get("icc_profile"))
```

Handed a real embedded profile — `iCCP`, e.g. `/System/Library/ColorSync/Profiles/Display P3.icc`,
536 bytes — that round-trips byte-identical. Which means the passthrough is untestable against a
file tagged `sips --matchTo` **sRGB**: it will read 0 bytes there forever, so a pipeline whose
inputs are all sRGB-tagged has a passthrough that has never carried anything. Tag a scratch copy
with a non-sRGB profile to test it — either tool will produce an `iCCP`:

```python
prof = Path("/System/Library/ColorSync/Profiles/Display P3.icc").read_bytes()
Image.open("in.png").convert("RGBA").save("tagged.png", icc_profile=prof)
```

Read the chunk list rather than trusting either tool's report — it is ~8 lines and it is the only
thing that answers "which kind of tag is actually in there":

```python
import struct
from pathlib import Path

d = Path(p).read_bytes(); i = 8
while i < len(d):
    ln = struct.unpack('>I', d[i:i+4])[0]; print(d[i+4:i+8].decode('latin1'), ln); i += 12 + ln
```
