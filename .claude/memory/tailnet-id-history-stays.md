---
name: tailnet-id-history-stays
description: The real tailnet id sits in this public repo's history; rewriting it out was declined 2026-10-09, don't re-propose it
metadata:
  type: project
---

The real tailnet id is in this public repo's history in two places: `claude/learnings/tailnet-scoped-service-binding.md` until a redaction commit on 2026-09-12, and `claude/memory/machines-private.secret.md` from 2026-08-04 to 2026-08-20, while that file was still committed in plaintext before transcrypt covered it. Neither file holds it at `HEAD`.

**Rewriting history to remove it was declined on 2026-10-09.** A rewrite of a public repo cloned on both machines forces a re-clone or reset on each, and the id names the tailnet without granting access to it, since joining still needs a login.

**How to apply:** keep new commits free of the id, which `/commit`'s confidentiality scan covers. A future scan that finds it in old commits is this known state, not a new leak, so don't propose a rewrite again.
