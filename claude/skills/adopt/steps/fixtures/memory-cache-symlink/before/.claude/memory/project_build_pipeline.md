---
name: Build pipeline
description: Where the build actually runs from, and why the root scripts are wrappers
type: project
---

The build runs from `web/`. The root-level scripts are thin wrappers that change directory
first, so running them from the root and running them from `web/` are the same build.
