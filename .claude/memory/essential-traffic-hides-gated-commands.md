---
name: essential-traffic-hides-gated-commands
description: CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC stays set by choice, so feature-gated slash commands never register — don't re-offer removing it
metadata:
  type: project
---

`claude/settings.json` sets `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. On 2026-09-14 the user was shown what that costs and chose to keep it. Do not re-raise removing it.

The consequence to recognise rather than re-diagnose: the flag puts the CLI in `essential-traffic` mode, which blocks the GrowthBook feature-flag fetch, so any slash command behind a gate reports **Unknown command** even though it is compiled into the binary. `/skill-doctor` is the case that surfaced this — it exists in the 2.1.270 binary with `isEnabled: () => <gate>`, and its report also lives in a Stats tab of `/plugin` that the same gate hides.

`DISABLE_TELEMETRY` and `DO_NOT_TRACK` are not a middle ground: the enablement predicate is true for any of the three, so every telemetry-off mode hides the same commands.

Also suppressed by the flag: `/bug`, `/feedback`, claude.ai plugin archive downloads, DesignSync, Projects, Remote Control, live-preview tunnels, update lookups. Unaffected: session API calls, auth, configured MCP servers, WebSearch/WebFetch, gateway model discovery.
