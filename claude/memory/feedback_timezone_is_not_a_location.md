---
name: feedback_timezone_is_not_a_location
description: an IANA timezone names a zone, not a place — never render one where a location belongs, never infer a city from one
metadata:
  type: feedback
---

An IANA timezone identifier (`America/Los_Angeles`, `America/Denver`) names a zone spanning half a continent. It is not a location. Never put one where a place belongs in UI or prose, and never infer a city from one.

**Why:** in an event list the subline rendered `2026-08-21 → 2026-08-23 · America/Los_Angeles`, which reads as the venue — the user pointed out that a timezone is not a location, twice: once about my prose, once about the shipped output. Separately I wrote that a convention was in "Seattle", inferred from `America/Los_Angeles`, and presented it as though the API had said so. The API said **Bellevue, WA**. `America/Denver` likewise turned out to be Aurora, CO, not Denver. The zone can never support the claim, because it covers everything from San Diego to the Canadian border.

**How to apply:** fetch the real location and store it in its own field — most event/venue APIs expose a city or formatted address alongside the zone. Where the zone genuinely matters, put it next to the clock times as a short abbreviation resolved at that instant (`times in PDT`), which reads as a zone rather than a place and stays correct across a DST boundary. Reserve the full identifier for operator-facing screens. See also [[feedback_no_guessed_facts]] — asserting the city was a guess dressed as a lookup.
