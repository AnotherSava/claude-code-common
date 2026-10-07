---
name: feedback_dont_quote_a_foreign_heading
description: Citing a document in another repo by its heading text breaks when that repo's own session rewords it; name the file and the fact instead
metadata:
  type: feedback
---

Cite a document in **another repo** by its file and the fact it establishes, never by a heading's exact words. Within one repo a heading is a stable landmark because the citing text and the heading move in the same commit. Across repos nothing couples them, and the session that rewords the heading cannot see what cites it.

**Why:** a memo in the `trips` repo cited `learnings/restic-backblaze-b2-backups.md` "under 'Assert the shape, not the presence'". A peer session correcting the same finding retitled that section and rewrote the sentence, so the citation named a heading that no longer existed — and nothing in either repo failed, because neither one can check the other. Re-pointing it at the new heading buys one edit's worth of accuracy and sets the identical trap again.

**How to apply:**
- Cite the file and state what it settles: "the lifecycle rule's four-field shape is in `learnings/restic-backblaze-b2-backups.md`".
- Quote a heading only when the citing text and the heading live in the same repo, so one commit moves both.
- The test: could a session that cannot see this file reword the thing being quoted? If yes, do not quote it.

Sibling of [[feedback_drift_proof_doc_anchors]] (where a range *ends*) and [[feedback_cite_the_source_not_the_count]] (what a *number* says) — the same decay from a third trigger, another repo's edit rather than an append. It narrows the global prose rule blessing "a file plus a stable landmark (a heading, a key name)", which does not distinguish same-repo from cross-repo.
