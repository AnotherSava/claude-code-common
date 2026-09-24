---
name: feedback_check_the_source_before_deriving
description: Before migrating stored data to a computed value, check whether the system that produced the data already holds the right one
metadata:
  type: feedback
---

Before writing a derived value over stored data, find out what wrote that row originally and whether that
source carried the field. A derived value is a guess dressed as a fix, and it looks authoritative precisely
because it was freshly computed.

**Why:** a fix to a derivation makes the new output feel like the truth, so the obvious next move is to
backfill it everywhere — and that move silently replaces curated values with inferred ones. Measured
2026-09-23 in the trips repo: a bug in the trip-location rule was real and fixed, and I then offered to write
20 re-derived locations over the stored ones. The correction was one question — *"didn't tripit already have
location field that you could use for past trips?"* — and it did, for every trip, in an export sitting in
the repo. The curated values were strictly better (a city name where the derivation said the suburb its hotel
was in), and half the changes I had proposed were the same place re-spelled, two of them worse.

**How to apply:** when stored data looks wrong, ask what imported it before asking how to recompute it. Look
for the original response, export or feed still on disk. If the source has the field, restore from it and
treat the derivation as the fallback for rows the source never covered. Then check what overwrites it — a
value that can be clobbered by a later derivation will be, so the restore is only half the fix, and the other
half is usually [[feedback_extend_schema_not_freetext]]'s split rather than a flag saying which kind a field
currently holds.
