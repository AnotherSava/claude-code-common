---
name: plannotator-update
description: Force-update the plannotator plugin by nuking stale caches and reinstalling fresh
allowed-tools: Bash
---

# Update Plannotator Plugin

Force-update the plannotator Claude Code plugin by clearing all cached data and reinstalling from the source repo.

## Why this exists

The plugin system caches a git clone of the marketplace repo at `~/.claude/plugins/marketplaces/plannotator/` and never re-fetches. This means `/plugin` reports "already at the latest version" even when a newer version exists. The only fix is to nuke the caches and reinstall.

## Steps

1. Remove the marketplace cache (the stale git clone — this is the root cause):
   ```
   rm -rf ~/.claude/plugins/marketplaces/plannotator/
   ```

2. Remove the plugin cache:
   ```
   rm -rf ~/.claude/plugins/cache/plannotator/
   ```

3. Tell the user to restart Claude Code, then run:
   ```
   /plugin marketplace add backnotprop/plannotator
   /plugin install plannotator@plannotator
   /reload-plugins
   ```

**Do not attempt the `/plugin` commands from this skill** — they require a fresh Claude Code session to work after cache deletion.
