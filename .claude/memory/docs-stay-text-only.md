---
name: docs-stay-text-only
description: Why this repo's documentation carries no images, decided 2026-09-24 — the switch itself is SCREENSHOTS=no in .claude/repo-flags
metadata:
  type: project
---

The switch is `SCREENSHOTS=no` in `.claude/repo-flags`, which `/screenshot-relevance`, `/docs-screenshot`
and `/wrap-up`'s scope check read. This file keeps the reasoning behind it.

Asked on 2026-09-24 whether to capture a screenshot for the `/github-status` README entry — which
describes a rendered box table and an HTML report entirely in prose — the answer was "leave it text only
for now".

**Why:** the repo holds zero image files, tracked or untracked, and no `docs/screenshots/` tree or
manifest. So the first screenshot is not one picture: it is that directory, a manifest, a capture script,
and a policy decision per frame thereafter.

**How to apply:** "for now" is a deferral rather than a permanent rule, so the answer can change — but it
changes because the user raises it, never because the gap hunt found the same absence again. Removing the
flag is what re-opens the question.
