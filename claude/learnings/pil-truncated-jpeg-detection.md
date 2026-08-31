# Detecting truncated JPEGs with Pillow

A JPEG whose file ends partway through the scan data still declares its full dimensions, because
the width and height live in the header. Browsers draw the scanlines that arrived and leave the
rest as whatever is behind the `<img>` — a grey slab, usually mistaken for a CSS or layout bug.

## Why the obvious check misses it

`Image.open()` is lazy. It parses the header and stops, so `.size` answers from the header alone:

```python
with Image.open(p) as im:
    w, h = im.size          # 640, 480 — even if the file holds 45% of the pixels
```

Any validity check built on "can I open it and get a size" therefore passes a truncated file. Only
`im.load()` actually decodes, and only with the default `LOAD_TRUNCATED_IMAGES = False` does it
complain:

```python
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = False   # the default, but set it — other code flips it globally

def truncated(path) -> bool:
    try:
        with Image.open(path) as im:
            im.load()
        return False
    except OSError:                        # "image file is truncated (N bytes not processed)"
        return True
```

The `N bytes not processed` in the message is **not** how much is missing — it is the unconsumed
tail of the buffer. A file missing 60% of its scanlines commonly reports 19 bytes.

## Measuring how much is actually missing

Flip the flag on, decode, and count up from the bottom: a truncated JPEG leaves its undecoded rows
a single flat value.

```python
import numpy as np

def missing_fraction(path) -> float:
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    with Image.open(path) as im:
        im.load()
        a = np.asarray(im.convert("L"), dtype=np.int16)
    h = a.shape[0]
    last = h - 1
    while last > 0 and a[last].std() < 0.5:
        last -= 1
    return (h - last - 1) / h
```

## Both tests, or you get false positives

The flat-rows test alone flags any photograph that genuinely ends in a uniform band — a dark
foreground, sky, a letterbox. In one 2374-photo set it produced exactly one false positive, a
complete file whose bottom quarter was uniformly dark. Require both signals:

```python
def visibly_incomplete(path, threshold=0.02) -> bool:
    return missing_fraction(path) > threshold and truncated(path)
```

The threshold matters as much as the test. Of 19 genuinely truncated files in that set, 6 were
missing 1–21 bytes — under 2% of the height, a line or two nobody sees. Flagging those puts a
"damaged" warning on images that look perfect. Report what a viewer can see, not what the bytes say.

## Cheap pre-filter

A complete JPEG ends with the EOI marker `FF D9` (allow trailing NULs):

```python
raw.rstrip(b"\x00").endswith(b"\xff\xd9")
```

Useful for scanning thousands of files quickly, but it is a necessary-not-sufficient check — some
encoders emit EOI after a short scan.

## Truncated on disk vs truncated in transit

Before assuming a bad download, compare against what the origin serves:

```
HEAD the original URL, compare Content-Length to the local size
```

Equal sizes mean the file was fetched completely and is broken at the source — nothing to re-fetch.
Sizes that are exact multiples of 4096 look like an interrupted transfer flushing whole blocks, and
that inference is wrong often enough to be worth checking rather than acting on: in one case six
files ended exactly on a 4096 boundary and the server held byte-identical copies of all six.
