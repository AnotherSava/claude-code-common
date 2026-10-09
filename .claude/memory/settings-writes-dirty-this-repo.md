---
name: settings-writes-dirty-this-repo
description: Any Claude Code command that writes user settings shows up as a pending commit here, because ~/.claude/settings.json is a symlink into this repo
metadata:
  type: project
---

A settings diff in this repo is usually not a decision anyone made. The file `~/.claude/settings.json` is a symlink to `claude/settings.json` here, so every Claude Code command that writes user settings lands in the working tree as a tracked modification — and because the whole file is rewritten, keys nothing touched can come back in a different order.

Observed cases, each of which swapped `timeout` and `async` in the `workflow-realism` hook entry and changed nothing else: `claude plugin install firecrawl@claude-plugins-official` on 2026-10-03, and `/effort` saving a default on 2026-10-07. Read the diff before attributing it to the session's work. Where a clean tree is wanted, `git checkout -- claude/settings.json` restores the committed order.

**The effort keys are deliberately absent.** The user removed `effortLevel`, `modelSettings` and `ultracode` on 2026-10-09. The level is not a decision about this repo — it gets picked from how much usage budget is left: *"i change it based on remaining limits, which is not related to the repository versioning"* (2026-09-19) — and `ultracode: true` made every session start at xhigh with standing multi-agent workflow orchestration, which pulls against that. Do not re-add any of the three to supply a missing default.

**Only one of them comes back on its own.** Saving an effort default writes to user settings, so changing the level recreates `modelSettings` here. No interactive toggle ever persists `ultracode`, so its absence holds. The routes that write nothing are the slider's `s` key, which needs Claude Code 2.1.257 or later (this machine was on 2.1.251 on 2026-10-09), and launch-time `claude --effort <level>` or `CLAUDE_CODE_EFFORT_LEVEL` — the env var makes `/effort` refuse to change the level while it is set. Mechanics in [[claude-code-effort-and-ultracode]].
