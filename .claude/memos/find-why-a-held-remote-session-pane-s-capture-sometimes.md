---
created: 2026-10-16 10:00:01
---

# Find why a held remote-session pane's capture sometimes loses the command's own error output

remote_session_create (claude/remote-session/lib.sh) holds a pane whose session command exits non-zero, and remote_session_clear_dead prints it with capture-pane on the next attach (start-here.sh, cc-session.sh). The point is that a rejected claude invocation leaves its error readable. On 2026-10-15 scratch tmux 3.4 servers (tmux -L <name>, -f /dev/null, detached, 100x30 or default size) gave mixed results: a stand-in script that printed 'fake: rejected ...' then exited 3 showed its line above 'Pane is dead (status 3, ...)'; but pane commands 'echo boom >&2; false', 'echo boom; sleep 0.3; false || {hold}' and 'echo docs-error; sleep 0.3; sh -c "exit 3"' showed only the 'Pane is dead' line. The old global remain-on-exit failed behaved identically, so it is pre-existing. Next step: reproduce with capture-pane -S - (scrollback) and -e, try with an attached client vs detached, and check whether remain-on-exit-format's scrollregion/linefeed write overwrites or scrolls away the output; if real claude errors can vanish, fix clear_dead (e.g. capture with -S -) or the format.
