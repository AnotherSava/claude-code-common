---
name: feedback_survey_key_uniqueness
description: Before matching records on a field, survey the stored data for values it shares across records; a non-unique key is non-unique in every direction
metadata:
  type: feedback
---

Before choosing a field to decide that two records are the same thing, query the real data for values of that field that sit on more than one record, and look for the fields that do tell those records apart. Then apply the answer to every comparison the key takes part in, not only the one that raised the doubt.

**Why:** on 2026-10-14 (trips) booking "references" (agency/order numbers) were added as a matching key. A review showed reference-to-reference matches merge sibling bookings, and the proposed fix kept reference-to-confirmation-code matches. The user pointed out that a number shared by several bookings is ambiguous in that direction too. A scan of the stored data then found order numbers covering a flight and two hotels, an outbound and its return, two bus tickets, and an account number on unrelated trips. The legs (flight, property, route) turned out to be what distinguishes them.

**How to apply:** when a key is proposed or a review questions one, run the collision query first, then state the rule for every pairing (key↔key, key↔other field). A key that only narrows to a group needs a second, distinguishing field before it counts as a match.
