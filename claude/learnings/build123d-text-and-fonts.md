# build123d: text, fonts, and getting a label out as one printable object

Measured on build123d 0.10.0 (OCCT font loader), Windows, 2026-10-17.

## Load a font from a file you commit, not from the system

`Text(txt, font_size, font=..., font_path=...)` loads the file at `font_path` when given, and otherwise looks `font` up among the installed fonts. A model built in a repo that is cloned on more than one machine should commit its font file and pass `font_path`: a system font present on one machine and absent on the other changes the geometry silently, which a regression signature then reports as drift.

Licence decides what can be committed. SIL OFL fonts (everything under `google/fonts/ofl/`) may be redistributed with their `OFL.txt` beside them. Fonts shipped with Windows (Segoe Script, Segoe Print, Ink Free, Gabriola) may not.

Check glyph coverage before offering a font — a script font often lacks Cyrillic or other scripts, and OCCT renders a missing glyph as nothing rather than failing:

```python
from fontTools.ttLib import TTFont
cmap = TTFont(path, lazy=True).getBestCmap()
missing = [c for c in set(text) if not c.isspace() and ord(c) not in cmap]
```

## Prefer a static font file to a variable one

OCCT loads a variable font's default instance, but variable fonts keep overlapping contours inside a glyph (static builds remove them). The same three-letter word gave 6 faces from Caveat's variable file and 5 from its static Regular. Overlapping faces extrude into overlapping solids. The project's own repository usually publishes static TTFs (for Caveat: `googlefonts/caveat`, `fonts/ttf/`) even where `google/fonts` carries only the variable file.

## Some glyphs come out as faces OCCT itself rejects

Caveat Regular's «н» (static and variable alike; Bold was fine) produces a single face whose `is_valid` is False although its outer wire is valid and has no self-intersecting edges. Extruding it gives an invalid solid, which fails any validity assertion downstream. `Shape.fix()` (ShapeFix) repairs it with the area unchanged, and returns the shape untouched when it is already valid, so it is safe to apply to every `Text`:

```python
sketch = Text(text, font_size=size, font=name, font_path=path).fix()
solid = extrude(sketch, amount=height)
```

Diagnose by extruding each character separately and listing the ones whose solid is invalid.

## Alignment and metrics

- `text_align=(TextAlign.LEFT, TextAlign.BOTTOM)` puts the **first baseline** at y = 0: descenders go negative (`р` reached −2.25 at size 10 while `а` started at +0.26). Use it whenever lines must be placed by baseline.
- `TextAlign.CENTER` vertically is not the glyph bounding box's centre; it comes from the font's metrics, so the box sits off-centre by a different amount per string. To centre a glyph box, align on the solid's bounding box afterwards.
- The font's line pitch can be measured instead of read from tables: the height of `Text("Х\nХ")` minus that of `Text("Х")`. For Caveat it equals `(hhea.ascent − hhea.descent) / unitsPerEm` = 1.26 em.
- Text geometry scales exactly linearly with `font_size` (widths and heights at 12.719 matched the size-10 values times 1.2719 to the third decimal), so a fitting search can measure each line once at a reference size.
- Extruded multi-glyph text is several disjoint solids, which a wrapper may hold as a `ShapeList` rather than one solid.

## A 3MF holds one object per solid

build123d's `Mesher.add_shape` expands a `Compound` into its children and writes one mesh object per solid. Text extruded from N disconnected glyphs therefore lands in a 3MF as N objects — a slicer importing the 3MF shows N parts. An STL has no objects, so writing all glyphs to one STL file keeps them together, but the 3MF does not.

To make the label one object, fuse a pane under the glyphs that is thinner than any layer height (0.01 mm), so it joins them into one solid and never prints:

```python
pane = Box(text_box.size.X, text_box.size.Y, 0.01)   # aligned to the text's bottom face, centred under it
label = pane.fuse(text)
```

Consequences to handle:

- Build the pane in the text's own frame and rotate the joined result afterwards; an axis-aligned pane under already-rotated text covers far more than the letters.
- Where the text is also used to engrave a recess, cut with the bare glyphs and export the joined version. Cutting with the joined one leaves a pane-shaped slit in the part.
- The pane spans the text's bounding box, so its corners can reach past the part's outline; intersect the label with the surface it stands on, extruded, to clip it.
