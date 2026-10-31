# Closing a push report with the review bookmark's state

Every skill that pushes ends its report the same way. Run `python ~/.claude/scripts/review_scope.py status`
(`python3` on macOS) and make its line the last line of the report, with any `not advanced` or `not pushed` line this
run printed quoted beside it, so whether the bookmark moved is read at the end rather than scrolled past mid-report.

The command reads origin and changes nothing, so it runs after a failed `advance` or `push` as safely as after a
successful one. Each skill that follows this file grants the command in its own `allowed-tools`, and
`claude/tests/push-notifies-peer.py` fails any skill the push rule clears that neither points here nor pushes
through `shared/push.py`, which prints the status line as its own last line.
