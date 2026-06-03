---
name: feedback-migrate-dont-degrade-persistence
description: Fix stale/wrong persisted data with a one-time cleanup/migration, not by switching a compute-once design to recompute-every-time
metadata:
  type: feedback
---

When persisted data is wrong or stale, fix it with a targeted one-time cleanup/migration — do NOT relax the system's "compute once and remember" semantics into "recompute every time" just so the bad value self-heals.

**Why:** In the BGA extension, table classifications used first-write-wins ("classify once via a costly probe, then remember it forever"). A bug had stored some wrong values, so I switched `setTableType` to overwrite-if-changed, reasoning that the next probe would correct them. The user pushed back: overwrite "only helps one time — now," and it permanently sacrifices the classify-once efficiency (every table open re-runs the probe from then on). The correct fix kept first-write-wins and ran a one-time, flag-guarded migration that dropped only the bad entries so they'd re-classify exactly once.

**How to apply:** When tempted to weaken first-write-wins / caching / "remember once" semantics to repair existing bad data, stop — that trades a permanent steady-state cost for a one-time problem. Instead do a flag-guarded one-time migration (or just clear the specific bad keys) and keep the efficient steady-state behaviour. Applies to any compute-once-and-persist value: classifications, derived caches, expensive lookups, backfilled fields.
