# Measuring text in generated SVG (no renderer available)

When generating SVG (or PDF) markup programmatically, there is no layout engine to ask for text widths — but precise widths are needed to place elements *after* a text run (e.g. an axis hint following a view title at a fixed gap) or to center a text+decoration block over content.

## Average-char-width estimates fail visibly

A `len(text) * avg_px` estimate (e.g. 8.4 px/char for 14 px bold) is wrong by ±20% depending on the mix of wide/narrow glyphs. Anything positioned "at a fixed gap after the text" then lands at a *different visible gap per string* — users notice immediately ("the spacing is inconsistent").

## AFM advance widths solve it

The Adobe core-14 AFM metrics for Helvetica (and Helvetica-Bold) are standardized per-glyph advances in 1/1000 em. **Arial is metric-compatible with Helvetica** (it was designed to match its advances), so browsers rendering `font-family="Helvetica, Arial, sans-serif"` on Windows produce widths that match the AFM sum almost exactly.

```python
_HELVETICA_BOLD_WIDTHS = {' ': 278, 'A': 722, 'a': 556, 'i': 278, 'm': 889, ...}  # 1/1000 em

def text_width(text: str, size: float) -> float:
    return sum(_HELVETICA_BOLD_WIDTHS.get(c, 600) for c in text) * size / 1000
```

Worked example: `draft_lib.py` in the build123d-models repo (view-header layout for dimensioned drafts).

## Derive spacing constants from the metrics

Instead of hardcoding a pixel gap, express it in typographic terms and compute it: "5× the word spacing" = `5 * text_width(' ', size)` (space advance is 278/1000 em → ≈3.9 px at 14 px → gap ≈ 19.5 px). The constant then survives font-size changes.

## Pitfalls

- **Non-ASCII glyphs**: em dash `—` (1000), en dash `–` (556), `×` (584), `°` (400), curly quotes (238) are easy to forget; a fallback default (~600) keeps unknown glyphs from breaking layout badly.
- Digits are all 556 in Helvetica (tabular), so numeric labels are safe with a single value.
- Bold vs regular have different tables — use the weight you render.
- This measures *advances*, not ink extents; fine for layout gaps, not for tight bounding boxes of italics.
