---
name: feedback_cheap_verification_is_not_unverified
description: Recording a claim as unverified is not a substitute for verifying it when the source is one fetch away
metadata:
  type: feedback
---

Marking a claim unverified is honest and it is not the end of the job. Where the thing that would settle it is
a download, a public API call or a local probe, fetch it — and do that before writing the uncertainty into a
memory, a doc or a reply, because a recorded "unverified" reads as settled-enough and nobody returns to it.

**Why:** 2026-10-11 in the trips repo, three airport codes a stored booking cited were missing from the
project's compacted airports table. I wrote "which side dropped them is unverified — whether OurAirports
retires a closed airport's code or our filter excluded closed rows cannot be read off anything here" into a
project memory and moved on. The dataset is public and 12 MB. The user asked for the completeness question to
be considered properly; one fetch answered it in full — of the 9,051 rows carrying an IATA code not one is
`type: closed`, and all three codes appear under no row at all — and that moved the conclusion from "cannot
tell" to "importing everything recovers none of them, and would drop 7 codes this snapshot still carries".

**How to apply:** when a claim turns on an external dataset, a published API, or anything a command can read,
price the verification before recording the doubt. A public file, a documented endpoint, or a query against a
database already open is cheap: fetch it. Reserve "unverified" for what genuinely cannot be reached from here
— a vendor's internals, a machine nobody has, a state that no longer exists — and say which of those it is,
per [[feedback_state_the_enforcement_reach]]. A second finding usually comes free: measuring the source also
tells you whether the local copy is better than it, which is what a snapshot of retiring identifiers often
is. Distinct from [[feedback_no_guessed_facts]], which forbids stating a guess as known — this one is about
the case where the guess was labelled honestly and the labelling became the whole of the work.
