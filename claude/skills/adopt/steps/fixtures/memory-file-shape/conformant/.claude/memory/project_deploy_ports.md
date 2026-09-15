---
name: project-deploy-ports
description: The dev server is pinned to 5174; a free-port fallback breaks the browser checks whose profile whitelists that origin
metadata:
  type: project
---

The dev server binds 5174 and refuses to start when the port is taken, rather than
picking the next free one. The browser profile the checks drive whitelists that exact
origin, so a fallback port produces a run that loads nothing and reports no error.

When the port is held, find what holds it and stop that, rather than moving the server.
