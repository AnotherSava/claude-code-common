---
name: feedback-desktop-first-then-phone
description: Build and refine the desktop look first; leave phone/narrow-width tuning to a later dedicated phase
metadata:
  type: feedback
---

While the look of a view is still being worked out, do not spend effort on how it behaves at phone widths — no
breakpoint-specific classes, no narrow-viewport measuring, no hiding elements on small screens. Build for the
desktop layout, and revisit the phone version once the design is settled.

**Why:** the design is still moving, so any narrow-width tuning is written against a layout that is about to
change and thrown away with it. Phone behaviour gets its own pass once the desktop look is final, where it can be
done once and coherently rather than guessed at per element.

**How to apply:** when a layout question only bites below roughly a tablet width (a column squeezed to nothing, an
element overflowing, a control too small to tap), note it and move on rather than adding `sm:`/`md:` handling.
Keep the markup width-agnostic. Raise the phone pass when the desktop look is signed off. Verification
screenshots and measurements should be taken at desktop widths.
