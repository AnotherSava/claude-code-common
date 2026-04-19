---
name: Attribution style for inherited projects
description: MIT compliance + prose acknowledgment style for substantial rewrites of other projects
type: feedback
---

When publishing a substantial rewrite that started from another MIT-licensed project:

- **Keep the original copyright line** in `LICENSE` (legally required by MIT). Add your own line BELOW it, chronologically:
  ```
  Copyright (c) YYYY <Original>
  Copyright (c) YYYY AnotherSava
  ```
- **Prose acknowledgment goes in `docs/index.md` only**, not README. This follows the bga-assistant convention where README is a short entry-point that links out, and `docs/index.md` is the site home where acknowledgments belong.
- **Format: "Initially based on [project] by [author]."** Short and neutral. Nothing more.
- **Do NOT list changes** ("Substantially rewritten — hooks, security fixes, ..."). User finds that ego-driven.
- **Do NOT call it a "fork"** unless a GitHub fork relationship actually exists on the repo. "Started as a fork of..." is misleading when the repo was created fresh (`gh repo create`) with no fork link.

**Why:** User rejected both the change-listing phrasing ("I don't like listing the changes") and the fork phrasing ("mentions fork that never happened") for these specific reasons. The "initially based on" form passes both filters.
