---
name: feedback_route_output_not_paste
description: A command only the user can run goes onto their clipboard, ready to paste, with its output teed to a file I read myself — never end with "paste the output"
metadata:
  type: feedback
---

When I hand the user a command *because only they can run it* (sudo, an interactive login, a GUI
step) and I need its result, route the output to a log under the repo's gitignored `tmp/`, teed by
the script itself (the default under **How to apply**), and read it myself. Never close with "paste
the output back".

**Why:** asking for a paste hands the user a second chore for something that is mine —
[[feedback_keep_your_half]] — and it is the slower path for them too: scroll, select, copy, paste,
hope nothing was truncated. A `tee` costs them nothing extra, since they still see it scroll. Asked
2026-09-14 why I hadn't at least offered a clipboard command, which was the right complaint about a
worse answer: `pbcopy` still needs a deliberate paste, and a sibling session overwrites the shared
clipboard before I get there ([[feedback_check_live_sibling_session]]).

**Put the command itself on the clipboard too.** Copying the output back is the chore the `tee`
removes; copying the command in is the other half, and it is mine as well. Asked 2026-10-30, after a
publish command was shown in a fence and the user had to select it: "why didn't you copy command to
run to the clipboard?" Showing it stays — the fence is what they read — but the copy is what they use.

**How to apply:**
- Copy the exact line they will submit, `!` prefix included when it is meant for the prompt:
  `printf '%s' '<cmd>' > /dev/clipboard` in Git Bash on Windows, `| pbcopy` on macOS. Read it back
  (`cat /dev/clipboard`, `pbpaste`) in the same call, and say in the reply that it is on the
  clipboard. Copy it last, right before the handover, for the reason the **Why** gives. `/dev/clipboard` is measured byte-exact both ways; `Get-Clipboard` appends a CRLF and
  transliterates non-ASCII, so its read-back never matches (`learnings/windows-clipboard-git-bash.md`).
  Not for a command carrying a secret, which never goes through `!` at all.
- Default for the command: a script that tees its own output (`exec > >(tee <repo>/tmp/<name>.log) 2>&1` at
  its top, as `publish` does), handed over as just `bash <absolute-script-path>`; then Read that log. The path is absolute because `!` runs in the session's current cwd, which an earlier `cd` has moved (`learnings/claude-code-auto-mode-permissions.md`). A hand-over carrying
  `2>&1 | tee <path>` itself is wide enough to wrap, and the paste splits after `| tee`
  (`learnings/claude-code-rendering.md`). Capture stderr as well — the diagnostic half of these commands goes there.
- `tmp/` because file tools refuse reads outside the working directories, per
  [[feedback_scratch_lives_in_project_tmp]]. `$TEMP` is a file I can write and never open.
- **Start a background wait for the result before handing the command over**, so its completion wakes me: the
  user's `!` run gives me no turn, a background command of mine exiting does. Wait on the log file for a line that
  only a finished run writes (`publish` has `skills/publish/scripts/await-publish.sh`), never on a fixed sleep. Asked
  2026-10-30: "why do i need to ping you after deployment is done - can you automate this too?"
- When the command genuinely cannot tee (a GUI toggle, a dashboard click), do not ask for a
  transcript of it — go and measure the resulting state myself afterwards.
- Copying the *output* back to me via the clipboard is the fallback for when no shared filesystem
  exists, not the first offer.
