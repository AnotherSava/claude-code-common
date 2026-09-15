---
name: No silent retries
description: A retry that logs nothing is indistinguishable from a first attempt in the log
type: feedback
---

Every retry writes a line naming the attempt number. Without it the log of a run that
succeeded on the third try is identical to the log of one that succeeded immediately.
