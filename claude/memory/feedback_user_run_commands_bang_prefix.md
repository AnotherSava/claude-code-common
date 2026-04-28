---
name: Run user-runnable commands myself instead of asking the user
description: When verifying my own work needs a command like `deploy`, `build`, `test`, etc., invoke it myself (via Skill or Bash) — don't write "re-run X" or suggest the user do it.
type: feedback
---

When I want to verify my own changes by running a command (`deploy`, `build`, `test`, app-launch scripts, etc.), I must run it myself. Don't write "Re-run `deploy` to verify" or "please run X" — just invoke the command via the Skill tool (if it's a registered skill like `deploy`, `build`, `release`) or via Bash.

**Why:** The user corrected this twice. After I said "Re-run `deploy` to verify", they pointed out I should `! deploy` it myself rather than ask. Verifying my own work is part of the work — pushing the verification step onto the user is a tax they shouldn't pay.

**How to apply:**
- After making changes that have a verify-via-command step, just run the command. Don't ask first, don't suggest, don't end the turn waiting on them.
- For commands available as Claude Code skills (`deploy`, `build`, `test`, `release`, `commit`, etc.), invoke them through the Skill tool.
- For ad-hoc shell commands, run via Bash.
- Genuine exceptions where it's still right to ask: destructive/irreversible commands (force-push, drop database), commands that require interactive user input (login flows), or anything explicitly outside the auto-mode safety envelope.
- This is a hard rule, not a hint. Auto mode reinforces it: "execute immediately, minimize interruptions, prefer action over planning."
