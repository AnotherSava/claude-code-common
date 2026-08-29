---
name: guard_input_must_survive_the_event
description: A guard that fires during teardown can't key on a signal that requires the thing being torn down
metadata:
  type: feedback
---

When writing a guard that must hold at teardown — a shutdown, an exit, a disconnect, an eviction — check that its discriminator is still readable *at that moment*. A signal derived from the live thing (a running pid, an open handle, a reachable socket, a session that answers) evaporates exactly when the guard is supposed to fire.

**Why:** on 2026-08-27 I gated row removal in claude-code-dashboard on `agent_pid`, resolved by walking the hook's ancestors for a live `claude` image. It was already reported on every event, so it looked free. But a session that is *shutting down* has no live ancestor to find, so the hook reported `null` — and the permissive fallback let a real killed-sibling `SessionEnd` delete a live sibling's row within minutes of shipping. The payload's `session_id` was right there the whole time: no process lookup, present unconditionally.

**How to apply:**
- Prefer a discriminator carried *in the message* over one derived from the environment at handling time.
- Ask "what does this read during the event I'm guarding against?" before "is this value already available?" — availability on the happy path proves nothing about the teardown path.
- When a guard has an `unknown → permit` fallback, the test that matters is **unknown against a *known* owner**, not unknown against unknown. My unit tests covered `(None, None)` and `(Some, Some)` and passed; the shipped failure was `(Some(owner), None)`, which I never wrote. Enumerate the fallback's arms against a populated state.

Related: [[feedback_not_run_is_not_pass]], [[feedback_instrument_first_fragile]].
