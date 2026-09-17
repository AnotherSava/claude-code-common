---
name: plannotator-update
description: Force-update the plannotator plugin by nuking stale caches and reinstalling fresh
allowed-tools: Bash
---

# Update Plannotator Plugin

Force-update the plannotator Claude Code plugin by clearing all cached data and reinstalling from the source repo.

## Why this exists

The plugin system caches a git clone of the marketplace repo at `~/.claude/plugins/marketplaces/plannotator/` and never re-fetches. This means `/plugin` reports "already at the latest version" even when a newer version exists. The only fix is to nuke the caches and reinstall.

## What this does not do

It updates the **plugin** and nothing else. The `plannotator` CLI in `~/.local/bin` is installed by `curl -fsSL https://plannotator.ai/install.sh | bash`, which also writes the `plannotator-*` skills into `~/.claude/skills/`. Neither path moves the other, so a box can run a current plugin against a months-old binary. Check `plannotator --version` separately — and read an empty answer as *old*, since the flag postdates earlier builds. Where both are stale, run the installer first: the plugin no longer ships `commands/` or `skills/`, so what is duplicated is only visible once the new version has written its half.

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

4. Verify the registry, which step 3 does not repair. Deleting the cache leaves `installed_plugins.json` untouched, so `/plugin install` answers "already installed globally" and writes nothing — leaving a recorded version and `installPath` that point at the directory step 2 removed. When `claude plugin list` disagrees with `~/.claude/plugins/cache/plannotator/plannotator/`:
   ```
   claude plugin update plannotator@plannotator
   ```
   Full mechanics in `~/.claude/learnings/claude-code-plugin-updates.md`.

**Do not attempt the `/plugin` commands from this skill** — they require a fresh Claude Code session to work after cache deletion. Step 4 is different: `claude plugin update` is a CLI command, not a slash command, and runs from here.
