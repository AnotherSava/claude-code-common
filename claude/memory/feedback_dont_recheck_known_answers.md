---
name: feedback_dont_recheck_known_answers
description: Don't re-run a check whose answer you already established; cite the earlier result instead
metadata:
  type: feedback
---

When an earlier probe already settled a question, cite that result — don't run the same check
again on a comparable input.

**Why:** Having established that the Wayback Machine holds no images from a dead site — six
full-size photo URLs queried, all "no capture" — I went back and started querying fifteen more
of exactly the same kind. The user stopped it: "whytf you keep checking wayback machine? haven't
we already scrapped _everything_?" The second sweep could not have found anything the first
didn't; it cost two minutes, hit a timeout, and learned nothing. Re-checking also signals the
first answer wasn't trusted, which invites re-litigating a settled point.

**How to apply:** Before reaching for an external check, ask whether this session already
answered it for a comparable case. If it did, state the earlier finding *with its scope* — "six
URLs, none captured; this archive holds pages, not images" — and move on. Re-probe only when
something has changed that could plausibly change the answer, and say what that is. Related:
[[feedback_live_values_source_of_truth]] is the opposite case, where the value genuinely moves
and a cached answer is the error.
