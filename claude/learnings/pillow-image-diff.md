# Diffing two screenshots with Pillow

The obvious one-liner reports "identical" for two RGBA images that differ:

```python
from PIL import Image, ImageChops
a, b = Image.open("before.png"), Image.open("after.png")   # both RGBA
ImageChops.difference(a, b).getbbox()                       # None, even when pixels differ
```

By default `Image.getbbox()` takes `alpha_only=True`: on an image with an alpha channel it trims
**transparent** pixels, so it looks only at the difference image's alpha band. Two opaque
screenshots have equal alpha everywhere, the alpha band of their difference is all zero, and the
box comes back `None` however much the colour changed. Measured on Pillow 12.1.1 with one pixel
changed in an otherwise identical pair:

| call                                               | result         |
|----------------------------------------------------|----------------|
| `difference(a, b).getbbox()` on RGBA               | `None`         |
| `difference(a, b).getbbox(alpha_only=False)`       | `(1, 2, 2, 3)` |
| `difference(a.convert("RGB"), b.convert("RGB")).getbbox()` | `(1, 2, 2, 3)` |

A `None` here is indistinguishable from a real "no change", which is how a recaptured screenshot
was once reported as pixel-identical to the old one while showing new text. Convert to RGB (or pass
`alpha_only=False`) before asking where two captures differ.

## Ignore antialiasing before trusting the box

Two captures of the same UI rarely match to the last level: text and slider edges shift by a shade
between runs. An unthresholded box then spans half the window and says nothing about what actually
changed. Threshold first, then list the changed bands:

```python
d = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L").point(lambda v: 255 if v > 8 else 0)
w, h = d.size
rows = [y for y in range(h) if d.crop((0, y, w, y + 1)).getbbox()]
# group consecutive rows into bands, then getbbox() each band
```

In the case above the raw box ran from the edited card down to a slider 850 px below; with a
threshold of 8 the only band left was the one line of changed text.
