---
name: feedback_extend_what_you_built
description: before reporting that something can't be done, check whether a tool you already built or already control can be extended to do it
metadata:
  type: feedback
---

Before reporting that something cannot be done, list what you already have — the tool you wrote this session, the API you already call, the file you already parse — and check each against the gap. Prefer extending one of them over accepting the limit.

**Why:** twice in one session (2026-09-01) I declared a limit that was not one, and the user had to point at the thing already in my hands. I said a cropped screenshot could not have transparent corners — while holding a PNG post-processor I had written an hour earlier, where a corner is just alpha. I said a chart's week was unreachable without a keypress — while already driving that app through an HTTP route I had added myself, which needed one more parameter. In both cases the limit was real for the *path I happened to be on* and dissolved one step sideways. What made it hard to see was having just finished building the thing: attention stays on the problem the tool was built for, not on the tool.

**How to apply:** treat "can't" as a claim that needs the same check as any other. Enumerate the capabilities already in reach before making it, and prefer a small extension of something you own to a workaround or a hand-back. If the limit survives that, say what *would* remove it rather than only that it exists — the user can then decide whether that cost is worth paying. Related: [[feedback_check_the_limit_is_real]].
