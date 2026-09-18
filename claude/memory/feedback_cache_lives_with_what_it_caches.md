---
name: feedback_cache_lives_with_what_it_caches
description: Derived data is stored with the thing it describes, not with the process that produced it.
metadata:
  type: feedback
---

Put a cache next to what it caches, not next to whoever filled it. Keyed by the producer, only the producer benefits and every other consumer starts cold; keyed by the subject, whoever asks next already has it.

**Why:** asked to cache per-repo work descriptions across two machines, I wrote one file on the machine running the report, holding entries for both machines' clones. The user rejected it — "not share, but if each machine stores cache of its own repos, both machines could use them = no cold start, no double work" — because the entries sat with the reporter rather than with the repos, so the second machine re-derived everything the first already had. Repartitioning it made each machine hold only its own clones, and the machine that owns a thing answers for it however the work is driven.

**How to apply:** ask who else will want this value before choosing where it lands, and put it where the *subject* lives rather than where the computation ran. When the owner is remote, have it answer for itself — resolve the entry on that side and carry the answer back — rather than collating into a central copy. Related: [[feedback_check_where_it_is_consumed]].
