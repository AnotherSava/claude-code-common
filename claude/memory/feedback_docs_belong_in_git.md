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

**A cache is none of them, and that is the question to ask first.** A local copy of data an upstream still
holds needs no tier at all, so check whether the system it came from still has it before widening a backup to
reach it. A directory of API responses and downloaded attachments is protected by that account existing, not by
restic — and what it owes instead is a line naming the upstream that refills it, or the next reader re-runs the
argument.

**Why:** I reported a 46 KB decision document as "the one artifact left unprotected, because the backup
covers `raw/` and `parsed/` but not `_scratch/`", and was asked: shouldn't that be protected by version
control, not by backup? It should. I had left a document in the scratch tier and then reasoned about
extending the *backup* to reach it — treating a symptom of mis-filing as a hole in coverage, and very
nearly widening a backup to carry something git should hold.

**Why, again on 2026-10-08:** I proposed pulling a gitignored directory into a nightly backup as the one thing
protected by nothing — the only local copy of a curated field for every trip, plus a dozen booking PDFs — and
was asked why it would be backed up when it can be re-downloaded. It can: the field is the source's own, from
a documented endpoint, and the PDFs are still in the mailbox they arrived in. The first case was a file in the
wrong tier; this one wanted no tier at all, and both times the reflex was to widen the backup.

**How to apply:** when something is "unprotected", ask whether an upstream still holds it, then which tier it
belongs in — before asking what would cover it where it currently sits. A document that only the backup can
save is in the wrong place. The
inverse holds too: data too large or too private for git does not become committable because it is
valuable — see [[feedback_check_destination_visibility]] before moving anything into a shared repo.
