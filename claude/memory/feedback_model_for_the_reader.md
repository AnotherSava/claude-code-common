---
name: feedback_model_for_the_reader
description: A data-modelling decision needs a consumer — enumerate a field only if the app computes on it, normalise an entity only if a screen reads it that way
metadata:
  type: feedback
---

Two data-modelling reflexes to check against an actual consumer before applying them. Both were caught by the
user on 2026-08-27 while building the trips itinerary app, and both errors are invisible once made.

**Don't enumerate a field unless the app computes on it.** Confirmation emails do not agree about what fields
exist. The relational instinct — give every field a column — is unbounded (a migration per new sender) and
silently drops whatever it did not anticipate. A typed schema written that way discarded Booking.com's check-in
PIN, Air Canada's aircraft type and Aeroplan number, and Amtrak's ticket number and auth code: all present in
the email, all on the floor, with no error anywhere. The user's argument was the right one — store the
open-ended tail as documents and choose in the UI what to show.

The line worth drawing: **typed if the app computes on it, a document entry if the app only displays it.**
Times, statuses and keys need to be indexable and joinable; a seat number, a wifi password or an aircraft type
is only ever rendered. A `{key, label, value}` entry keeps the sender's own wording and stays individually
renderable, orderable and hideable.

**Don't normalise an entity unless a screen reads it that way.** The same app grew a shared `places` table with
a dedup key so a hotel stayed at twice would be one row. Asked "why do you need deduplication", the honest
answer was that nothing needed it: no screen asked "everything at this hotel", and resolving a timezone was a
local table lookup plus an offline function, so there was no geocoding call to save. Normalising was reflex,
not requirement — and it had been used as an argument for the wrong storage engine.

**Why:** neither failure announces itself. A dropped field looks exactly like a field the sender never sent,
and a needless join looks like good hygiene. Both only surface when somebody asks what the structure is *for*.

**How to apply:** before adding a column, ask what code reads it — if the answer is "the detail page prints
it", it is data, not schema. Before extracting a shared table, name the query that joins on it; if you cannot,
embed it. When challenged on either, check rather than defend: the challenge is usually right, because the
person asking is the one who knows what they will read.

Complements [[feedback_extend_schema_not_freetext]] — that forbids burying structure in a free-text comment,
and a labelled document entry is not free text; it is the case that rule does not cover. Same family as
[[feedback_no_premature_abstraction]], applied to data rather than to code.
