---
name: docs-stay-text-only
description: Why this repo's documentation carries no images, decided 2026-09-24 — the instruction itself is in CLAUDE.md, where /docs-relevance reads it
metadata:
  type: project
---

The instruction lives in `CLAUDE.md`, because that is the file `/docs-relevance` reads for a repo's
documentation rules and this one lived here where the skill never saw it. This file keeps the reasoning
behind it.

Asked on 2026-09-24 whether to capture a screenshot for the `/github-status` README entry — which
describes a rendered box table and an HTML report entirely in prose — the answer was "leave it text only
for now".

**Why:** the repo holds zero image files, tracked or untracked, and no `docs/screenshots/` tree or
manifest. So the first screenshot is not one picture: it is that directory, a manifest, a capture script,
and a policy decision per frame thereafter.

**How to apply:** "for now" is a deferral rather than a permanent rule, so the answer can change — but it
changes because the user raises it, never because the gap hunt found the same absence again. Removing the
`CLAUDE.md` paragraph is what re-opens the question.
