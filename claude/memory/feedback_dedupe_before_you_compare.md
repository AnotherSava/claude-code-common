---
name: feedback_dedupe_before_you_compare
description: A count of records returned by a paginated source is not a count of distinct things; dedupe on the identity key before comparing two sets or reporting the comparison
metadata:
  type: feedback
---

Counting the records a paginated API handed back is not counting the things it described. Dedupe on the
identity key **first**, and do it before any comparison — not after the conclusion is already spoken.

**Why:** on 2026-09-03 I compared a vendor export against a full API sweep of the same account and told
the user the API had returned "95 more turns than the export". It had returned 297 fewer. Summing
`entries[]` across pages gave 5,088; deduping on `backend_uuid` gave 4,791. Paginated pages overlapped,
`first_entry`/`latest_entry` repeated members of `entries`, and 66 directories were aliases of threads
already counted under another id. The inflated number did not merely exaggerate a margin — it inverted
the finding, turning "the API is a strict subset of the export" into its opposite, and the user acted on
that for a full exchange before asking a question that exposed it. The same undeduped count then reached
a manifest I wrote, where an adversarial audit found it again.

The trap is that the raw count is *plausible*. It is the right order of magnitude, it comes from real
data, and nothing about it looks wrong — so it survives exactly as long as nobody re-derives it.

**How to apply:** before comparing two datasets, state the identity key for each side and reduce both to
sets on that key; a comparison of multisets is a comparison of transport artefacts, not of content. When
a source paginates, assume overlap until measured, and report the duplicate count alongside the distinct
count so the gap is visible rather than silent. Put the dedupe in the code that ships, not in the
analysis — the same wrong number reaches a manifest, a README and a chat answer otherwise. And when a
comparison reverses a previous claim, say so plainly rather than restating the new number as if it were
the first: see [[feedback_no_guessed_facts]] for the adjacent failure of asserting an unverified figure,
and [[feedback_cite_the_source_not_the_count]] for counts that rot in documents rather than at derivation.
