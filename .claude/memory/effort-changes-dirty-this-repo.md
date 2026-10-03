---
name: effort-changes-dirty-this-repo
description: /effort and other Claude Code writes to ~/.claude/settings.json go through the symlink into this repo, so each one appears as a pending commit here
metadata:
  type: project
---

Changing effort level dirties this repo. `~/.claude/settings.json` is a symlink to `claude/settings.json` here, and `/effort` saves the level per model under `modelSettings` in user settings — so the write lands in the working tree as a tracked modification.

The value is not a decision about this repo. The user picks it from how much usage budget is left: *"i change it based on remaining limits, which is not related to the repository versioning"* (2026-09-19). Treat it as incidental to whatever else is being committed rather than as a configuration change worth its own commit or message line.

**How to stop it:** in the `/effort` slider or the `/model` picker, press `s` instead of `Enter` — that applies the level to the session and writes nothing. It needs Claude Code v2.1.257 or later; this machine was on 2.1.251 on 2026-09-19. Until then the only non-persisting routes are launch-time: `claude --effort <level>` and `CLAUDE_CODE_EFFORT_LEVEL`.

Two effort keys now coexist in the file — a top-level `effortLevel` and the per-model one under `modelSettings` — and they can disagree, so read both before reporting what the configured level is. Saving also reorders the `if`/`command` keys in the four windows-link-guard hook entries; that is inert, since JSON key order binds nothing and the commit gate passes either way, and it was deliberately left alone on 2026-09-19 rather than fought.

**Effort is not the only trigger.** Any Claude Code command that writes user settings rewrites the whole file and can reorder keys inside it: `claude plugin install firecrawl@claude-plugins-official` on 2026-10-03 swapped `timeout` and `async` in the `workflow-realism` hook entry, with no other change. So a settings.json diff after a plugin, model or config command is this symlink and not a configuration decision — read the diff before attributing it to the session's work, and a path-scoped `git checkout -- claude/settings.json` restores the committed order where a clean tree is wanted.
