---
name: feedback_status_colour_vs_page
description: A status colour is judged against the page it sits on, not only against its own text — pale tinted fills pass ink contrast and are still invisible
metadata:
  type: feedback
---

A tinted status badge can pass every contrast check you thought to run and still be unreadable, because the check
everyone runs is the wrong one. Measure **two** ratios: the ink against its own fill, and the **fill against the
page behind it**.

Real case — seat-count pills drawn as mid-tone text on a pale tint of the same hue:

| | ink on fill | fill on page |
| --- | --- | --- |
| green `#2f7a4d` on `#e7f4ec` | 4.62 | **1.09** |
| amber `#8a6100` on `#fdf1da` | 4.95 | ~1.05 |
| red `#8a3232` on `#f9e9e9` | 6.91 | ~1.10 |

Every one passes AA on the column people check. The second column is why the user said *"colours are too subtle,
and also green/red is poorly readable on light background"* — three fills at ~93% lightness on a ~96% page are
not three colours, they are three whites, and at 10px the hue is something you have to go looking for.

**How to apply.** Fill the badge with the strong colour and put near-white ink on it; both ratios then clear 5:1
at once. The ink can be a token that **inverts with the scheme** — `text-background` in a Tailwind theme is
near-white in the light scheme and near-black in the dark one, which is exactly the inversion the fills already
make, so one class works in both and no per-state ink token is needed. Check the existing palette before adding
tokens: colours defined as *text* on a tint are usually already dark enough to carry white ink as *fills*.

Not in conflict with [[feedback_understated_affordances]], which governs **action** affordances — those stay
muted at rest and save colour for hover. A status badge has the opposite job: it is read, not clicked, and it has
to survive being glanced at in a dense list. Related: [[feedback_glyph_not_caps]] (the same "grey is what the eye
skips" failure, solved with a glyph where there is no element to recolour) and [[feedback_chart_neighbour_contrast]]
(adjacent-swatch contrast beats a theoretically-even hue spread).
