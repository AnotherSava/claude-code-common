---
name: feedback_match_the_manual_shape
description: when automating something the user does by hand, invoke their own wrapper and reproduce its shape — not a lean equivalent that "does the same thing"
metadata:
  type: feedback
---

When automating something the user already does by hand, reproduce the shape their own tooling produces — including the parts that look incidental. Do not build the lean equivalent that appears to do the same thing.

**Why:** twice in one session (2026-08-31) the lean version was wrong in a way that only surfaced at the end. Launching `claude` as an agterm session's own process is the obvious reading of "start a session" — and it closes the moment Claude exits, leaving nothing to walk up to, which was the actual requirement. Separately, the `--continue` the user expected was not a flag anyone would have thought to pass: it comes from their own `claude()` shell function, so going *through* the function is what makes the result identical rather than merely similar. Both failures look like working code and only disagree with the user at the moment they go to use it.

**How to apply:** find what the user's own path actually runs — their shell function, alias, or wrapper script — and invoke that, rather than the underlying binary with flags you chose. Read the wrapper before assuming you know what it adds. When a lean equivalent is genuinely necessary, say which properties of the manual shape it drops rather than presenting it as the same thing. Related: [[feedback_verify_before_justifying]].
