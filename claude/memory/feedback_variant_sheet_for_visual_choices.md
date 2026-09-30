---
name: feedback_variant_sheet_for_visual_choices
description: tuning a subjective visual property (a colour, a weight, a spacing) gets one HTML page of every candidate on the second adjustment, not another deploy-and-screenshot cycle
metadata:
  type: feedback
---

When a subjective visual property is being tuned — a colour, a weight, a spacing — generate every candidate into one HTML page and publish it, rather than deploying one candidate at a time and asking.

**Why:** tuning one pill colour on 2026-09-30 took four deploy-and-screenshot cycles (dark green, then white, then lighter text, then "make white a bit darker") before the user asked for "an html with multiple sets of all kind of pill varying colour of background and text — i'll see which one is better". One page of sixteen candidates settled it in a single round, and the answer was nowhere near where the iteration was heading. A deploy cycle costs minutes and shows one answer; the page costs one file and shows all of them at once, which is also the only way a *comparison* is visible at all.

**How to apply:** the trigger is the **second** adjustment to the same property — at that point stop iterating and build the sheet. Three things make it worth looking at rather than a swatch grid:

- Show each candidate in its real context, not alone. The pill mattered beside the bright unread state it must not outshout and the grey one it must not be mistaken for, and neither relationship is visible in a swatch.
- Reuse the shipped CSS at shipped sizes, copied rather than approximated, so the page is not its own separate design.
- Number the candidates and say which one is currently deployed, so the reply can be a number.

Distinct from [[feedback_image_report_always]], which is about reporting on images that exist, and from [[feedback_show_the_artifact_with_the_ask]], which is about choosing between artifacts that already exist. This one is about *generating* the alternatives instead of serialising them through the user.
