---
name: memo-surfacing-session-start-only
description: The backlog never surfaces unasked; the session-start status bar was removed 2026-11-19, and a count in place of the list and a task-completion listing were declined earlier
metadata:
  type: project
---

The backlog surfaces nowhere unless asked for. CLAUDE.md's Memos section carries the rule.

**The session-start status bar was removed on 2026-11-19**, at the user's request: they no longer
wanted it, and it cost too much. It needed `statusLine.refreshInterval: 2` so the list appeared
while the session was idle, and on the Windows machine about 10 sessions each spawning
`bash -c` plus Python every 2 s slowed every process start there from ~25 ms to 0.6–1.9 s and made
typing lag by seconds (`skills/hooks/references/performance.md` has the figures). The
pick-by-number on the first prompt went with it, since it read the bar's state.

Two softer versions were declined on 2026-10-06, so neither is re-proposed:

**A count in place of the list** — "30 open memos" after a push — reintroduces the same
interruption at a tenth the size and tells the reader nothing they can act on.

**A task-completion listing** of the memos captured during that task was offered as a middle
option and declined. 37 memos were open that day, so the post-push listing ran 37 lines and
buried the notices that need reading — the push result, the CI verdict, a peer handoff.
