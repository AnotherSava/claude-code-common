---
name: Deploy target
description: Staging first, then production, and never the two in one command
type: project
---

The deploy script takes the host as its first argument and defaults to staging. Production
is named explicitly, so no deploy reaches it by forgetting an argument.
