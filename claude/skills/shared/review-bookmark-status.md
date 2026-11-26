# Reporting the review bookmark around a push

Every push is bracketed by two bookmark lines: before it, where the bookmark will stand once the push is done; after
it, where it stands. `shared/push.py` prints both itself. A push made any other way — a `--force-with-lease` branch
push, a tag push, a branch deletion — runs `python ~/.claude/scripts/review_scope.py forecast` (`python3` on macOS)
immediately before the `git push` and `python ~/.claude/scripts/review_scope.py status` once it is done, and reports
each line as it stands. A push standing in for `push.py`'s takes its order from the "After the push" section of
`shared/sync-and-push.md`: the forecast takes `--publish`, and `status` follows `review_scope.py push` and the peer
notice. Any other push, and a push git refuses, runs `status` immediately after the `git push`. Without `--publish`
the forecast leaves origin's bookmark where it is, and says so when the local one differs.

Every skill that pushes also ends its report the same way: `python ~/.claude/scripts/review_scope.py status` again,
its line made the last line of the report, with any `not advanced` or `not pushed` line this run printed quoted
beside it, so whether the bookmark moved is read at the end rather than scrolled past mid-report.

Both commands read origin and change nothing, so they run after a failed `advance` or `push` as safely as after a
successful one. The `/pr-create`, `/pr-merge` and `/release` skills grant both in their own `allowed-tools`, which
pre-approves a call only within the turn that invoked the skill
(`~/.claude/learnings/claude-code-auto-mode-permissions.md`). The `/upstream-sync` skill grants neither, since it
pushes only after the user types an answer, which ends that turn; its calls are decided like any other command.
`claude/tests/push-notifies-peer.py` fails any skill the push rule clears that neither points here nor pushes
through `shared/push.py`.
