---
name: docs-stay-text-only
description: This repo's documentation carries no images by choice, decided 2026-09-24 — do not re-raise the screenshot gap that /docs-relevance finds every run
metadata:
  type: project
---

The documentation here stays text-only. Asked on 2026-09-24 whether to capture a
screenshot for the `/github-status` README entry — which describes a rendered box
table and an HTML report entirely in prose — the answer was "leave it text only
for now".

**Why:** the repo holds zero image files, tracked or untracked, and no
`docs/screenshots/` tree or manifest. So the first screenshot is not one picture:
it is that directory, a manifest, a capture script, and a policy decision per
frame thereafter.

**How to apply:** `/docs-relevance` step 4 hunts for sections that describe
something visual and carry no image, and this README has several — the box table,
the HTML report, the contact sheet. It will find the same gap on every run. Do not
re-raise it. "For now" is a deferral rather than a permanent rule, so the answer
can change, but it changes because the user brings it up, not because the check
found the absence again. Deleting this file is what re-opens the question.
