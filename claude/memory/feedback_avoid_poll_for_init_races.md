---
name: feedback_avoid_poll_for_init_races
description: Don't mask a startup/init race with a retry poll — fix init ordering + do one sequenced read (or an explicit readiness handshake); reserve polling for when there's no cheaper deterministic option
metadata:
  type: feedback
---

When a value is read wrong because of a startup/initialization race (the consumer reads before the producer is ready), do NOT paper over it with a retry/poll loop. The user flagged a bounded config-retry poll as not-good-practice and expected proper sequencing: *"I'd expect some way to have steps in sequence — fully initialize the back-end, then start the front-end."*

**Why:** a poll hides the race instead of removing it, and adds a loop a reviewer has to reason about. The correct fix makes the ordering right: initialize the producer as early as possible, then have the consumer read the authoritative value **once** at a point where the producer has demonstrably finished — a single sequenced read, not a loop.

**How to apply:**
1. Move the producer's init before the consumer can read it (e.g. manage the state first).
2. Do ONE authoritative re-read at a definite "producer is up" point — e.g. after other round-trips prove it's ready — rather than looping until the value looks right.
3. Keep a cheap event/backstop for the residual.

Reach for a full readiness **barrier** (e.g. a `tokio::sync::Notify` the consumer awaits, or a `wait_until_ready` command) only when the race is wide/high-stakes AND there's no cheap self-healing backstop. Weigh the failure modes: a missed sequenced read is benign and self-heals (read a stale value once, corrected by the backstop); a mis-implemented barrier can hang forever (e.g. `Notify::notify_waiters` firing before the waiter parks → lost wakeup). Don't trade a harmless miss for a hang. Related: [[feedback_fix_at_source]]. Concrete instance: the tauri-dashboard `get_config` mount race (auto_resize read as `'none'` → auto-resize disabled), fixed by managing `ConfigState` first in `setup()` + one authoritative re-read at end of mount.
