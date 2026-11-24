---
name: repo-flags-value-decides
description: A repo flag in .claude/repo-flags is decided by its value alone, never a default inferred from another repo property; unset asks, or keeps an existing offer and records the answer after a decline (RELEASES)
metadata:
  type: feedback
---

A key in `.claude/repo-flags` is decided by its value alone. When it is unset, the reading skill asks the
user which value to record. It does not infer a default from some other property of the repo.

**Why:** on 2026-11-21 the user rejected keeping screenshot-relevance's private-repo default beside
`SCREENSHOTS`: "just make it based on screenshots value, and ask what value to set if not set - no matter if
repo is private or not". The private-repo default was removed for this.

**How to apply:** a new key either asks when it is unset or keeps a skill's existing offer, and only when a
decline then records the answer. `RELEASES` is the second kind: the release offer still appears, and
declining it while the key is unset asks whether the repo is never released and records `RELEASES=no` or
`RELEASES=yes` either way; once `yes` is set, a decline asks nothing. See [[docs-stay-text-only]].
