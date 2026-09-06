---
name: feedback_image_report_always
description: Reporting anything about images or screenshots means building the HTML contact sheet and linking it — never prose, never images read into the transcript
metadata:
  type: feedback
---

Any time a reply reports on images or screenshots — what changed, what is stale, what was captured,
cropped, keyed or bordered, or what a comparison shows — **build the HTML contact sheet and hand over
its `file:///` URL.** The template and layout rules are in
`~/.claude/skills/documentation/references/contact-sheet.html`. This holds whether or not the work
came from a `/documentation` run; the trigger is *reporting about pictures*, not which skill is loaded.

**Why:** the user has asked for this repeatedly and had to ask again each time, because every instance
came with a reason it seemed unnecessary. The reasons are always the same shape and always wrong:

- *"The change is a single pixel, so a sheet would show nothing."* — it shows nothing **as prose**.
  That is an argument for magnified corner crops, not against the sheet.
- *"The change is uniform across fourteen images, so it would be mostly noise."* — uniformity is a
  claim about the images, and a claim about images is the thing a sheet exists to let them check.
- *"They have already seen a representative example inline."* — a representative example is a sample
  the reader did not choose. They cannot see the one that went wrong.
- *"This was memo work, not a documentation run."* — the pictures do not know which skill produced
  them.

Images read into the transcript are explicitly **not** a substitute, and the skill already says so:
they arrive in the order they were read, split by tool output, and cannot be paired up or flipped
between. Every time this rule was skipped, the thing that got missed was visual — a black container
line down one edge, a stroke coloured from a text pixel, a blue section fill — and none of it was
catchable in prose.

**How to apply:** build the sheet *before* writing the summary, and let the summary point at it rather
than duplicate it. Show every image, not just the ones that changed. Include the theme toggle so
claims about light and dark are testable, and magnified corner crops whenever the change is smaller
than the eye can find at page scale. Open the finished page in a browser before linking it — the
check that catches what grepping the HTML cannot. See [[user_screenshot_location]] for where
user-supplied images arrive.
