---
name: feedback_route_output_not_paste
description: When handing over a command whose output I need back, tee it to a file I read myself — never end with "paste the output"
metadata:
  type: feedback
---

When I hand the user a command *because only they can run it* (sudo, an interactive login, a GUI
step) and I need its result, route the output to a file under the repo's gitignored `tmp/` with
`2>&1 | tee <path>` and read it myself. Never close with "paste the output back".

**Why:** asking for a paste hands the user a second chore for something that is mine —
[[feedback_keep_your_half]] — and it is the slower path for them too: scroll, select, copy, paste,
hope nothing was truncated. A `tee` costs them nothing extra, since they still see it scroll. Asked
2026-09-14 why I hadn't at least offered a clipboard command, which was the right complaint about a
worse answer: `pbcopy` still needs a deliberate paste, and a sibling session overwrites the shared
clipboard before I get there ([[feedback_check_live_sibling_session]]).

**How to apply:**
- Default: `sudo bash <script> 2>&1 | tee <repo>/tmp/<name>.log`, then Read that file next turn.
  `2>&1` matters — the diagnostic half of these commands goes to stderr.
- `tmp/` because file tools refuse reads outside the working directories, per
  [[feedback_scratch_lives_in_project_tmp]]. `$TEMP` is a file I can write and never open.
- When the command genuinely cannot tee (a GUI toggle, a dashboard click), do not ask for a
  transcript of it — go and measure the resulting state myself afterwards.
- `pbcopy` is the fallback for when no shared filesystem exists, not the first offer.
