---
name: settings-writes-dirty-this-repo
description: Any Claude Code command that writes user settings shows up as a pending commit here, because ~/.claude/settings.json is a symlink into this repo
metadata:
  type: project
---

A settings diff in this repo is usually not a decision anyone made. The file `~/.claude/settings.json` is a symlink to `claude/settings.json` here, so every Claude Code command that writes user settings lands in the working tree as a tracked modification — and because the whole file is rewritten, keys nothing touched can come back in a different order.

Observed cases, each of which swapped `timeout` and `async` in the `workflow-realism` hook entry and changed nothing else: `claude plugin install firecrawl@claude-plugins-official` on 2026-10-03, and `/effort` saving a default on 2026-10-07. Read the diff before attributing it to the session's work. Where a clean tree is wanted, `git checkout -- claude/settings.json` restores the committed order.

**The effort keys are deliberately absent.** The user removed `effortLevel`, `modelSettings` and `ultracode` on 2026-10-09. The level is not a decision about this repo — it gets picked from how much usage budget is left: *"i change it based on remaining limits, which is not related to the repository versioning"* (2026-09-19) — and `ultracode: true` made every session start at xhigh with standing multi-agent workflow orchestration, which pulls against that. Do not re-add any of the three to supply a missing default.

**Press `s` rather than Enter in the `/effort` slider.** That applies the level to the session and writes nothing, which is what keeps the keys out of the tree. It needs Claude Code 2.1.257 or later, and this machine was upgraded from 2.1.251 to 2.1.295 on 2026-10-09 for exactly that.

Enter instead saves a default, which writes user settings and so recreates `modelSettings` here — the one key that returns on its own. No interactive toggle ever persists `ultracode`, so its absence holds without anyone maintaining it. The launch-time routes are `claude --effort <level>` and `CLAUDE_CODE_EFFORT_LEVEL`, and the env var makes `/effort` refuse to change the level at all while it is set. Mechanics in [[claude-code-effort-and-ultracode]].

**The model key stays out too.** On 2026-11-15 `/model`, saving Opus 5.5 as the default for new sessions, wrote `"model": "opus"` here, and the user chose to restore the committed file rather than keep it, as with the effort keys.

**Since 2026-11-19 a misclick no longer changes the default model, and the keys clean themselves up on the next model switch.** After a `/model` save to Fable on 2026-11-18 carried into another project's sessions, the user chose both guards. `ANTHROPIC_MODEL: "opus"` in the settings `env` block wins over a saved `model` key at launch, while `/model` still switches the running session with Enter or `s`. The `PostModelSwitch` hook `claude/hooks/model-default-guard.py` deletes `model`, `modelSettings` and `effortLevel` from the file after every model switch. An effort-only save fires no hook, so `modelSettings` can still show up here until the next model switch, and pressing `s` still matters for effort.
