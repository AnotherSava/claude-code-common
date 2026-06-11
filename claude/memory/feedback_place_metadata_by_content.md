---
name: feedback-place-metadata-by-content
description: Place project metadata files by content ownership (next to the artifact they describe), not in .claude/ tool convention
metadata:
  type: feedback
---

Place project metadata files by content ownership, not tool convention. When a file describes the product (e.g. Chrome Web Store listing data), it belongs where that content lives — `cws-publish.json` next to `manifest.json` at the unpacked-extension root — not buried in `.claude/` just because a Claude skill reads it.

**Why:** `.claude/` hides product-relevant data from anyone browsing the repo, and per-tool placement breaks when a repo hosts several instances (multiple extensions in one repo each get their own file next to their manifest). Came up 2026-06-06 when the `publish-chrome-extension` skill's listing file was first placed in `.claude/` and the user moved it to the extension root.

**How to apply:** before defaulting a skill's per-project file into `.claude/`, ask whether the content is about the project itself; if so, anchor it to the artifact it describes.
