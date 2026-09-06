---
name: feedback_docs_belong_in_git
description: Documents are protected by version control, data by the backup tier, and scratch by nothing on purpose — fix a mis-tiered file by moving it, not by widening the backup
metadata:
  type: feedback
---

Three tiers, three different protections, and a file in the wrong one is a filing error rather than a
coverage gap:

- **Version control** — documents, decisions, code. Anything a person wrote and would want the history of.
- **The backup tier** (restic, object storage, whatever) — the corpus that is too large or too private for
  git.
- **Scratch** — protected by nothing, *by design*. That is what makes it scratch.

**Why:** I reported a 46 KB decision document as "the one artifact left unprotected, because the backup
covers `raw/` and `parsed/` but not `_scratch/`", and was asked: shouldn't that be protected by version
control, not by backup? It should. I had left a document in the scratch tier and then reasoned about
extending the *backup* to reach it — treating a symptom of mis-filing as a hole in coverage, and very
nearly widening a backup to carry something git should hold.

**How to apply:** when something is "unprotected", ask which tier it belongs in before asking what would
cover it where it currently sits. A document that only the backup can save is in the wrong place. The
inverse holds too: data too large or too private for git does not become committable because it is
valuable — see [[feedback_check_destination_visibility]] before moving anything into a shared repo.
