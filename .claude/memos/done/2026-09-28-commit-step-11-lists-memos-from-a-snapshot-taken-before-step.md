---
created: 2026-09-14 06:15:24
---

# commit step 11 lists memos from a snapshot taken before step 6 closed them

The Pending memos entry in commit/SKILL.md's Context block is a `!` command, so it is evaluated once when the skill loads — before step 6 runs. Step 6 is where an implemented memo is closed with memos.py done, and step 11 then renders that stale snapshot as the closing backlog.

Step 11's own text asserts the opposite: "A memo this change set implemented was already moved into done/ and folded into the commit back in step 6, so it won't appear here — don't re-offer it." It will appear, because the listing it reads predates the move. The user is then shown a memo the same commit just closed, immediately after being told that cannot happen.

Pre-existing, and not caused by the batch-selection work of 2026-09-13. Found while reviewing that change; reported at the time and never disposed of until /wrap-up on 2026-09-14.

Worth doing: have step 11 re-read the backlog rather than trusting the load-time snapshot — `python ~/.claude/skills/memo/memos.py list --width 120` at that point — or, if the extra call is unwanted, change the step's text to say the Context listing predates the closes and that memos moved in step 6 must be excluded by hand. The first is preferable: a step that silently contradicts its own guarantee is the shape feedback_not_run_is_not_pass.md is about.
