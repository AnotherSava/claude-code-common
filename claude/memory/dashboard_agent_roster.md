---
name: dashboard_agent_roster
description: The Claude Code Dashboard answers "what sessions are running, on which machine, doing what" over GET /api/agents, merged across both machines
metadata:
  type: reference
---

Ask the dashboard rather than the machine when a task needs to know what Claude sessions exist:

```
GET http://127.0.0.1:9077/api/agents     # port is server_port in the dashboard's config.json
```

It answers for this machine **and** its synced peers in one read-only call, which is what Claude
Code's own session listing cannot do — that one sees only the local box. Each row carries the
project, the device, the status and the task line the dashboard displays, so it settles "does a
session for project X exist, where, in what state, and how fresh is that answer" without reaching
the other machine at all.

Two arrays, and they mean different things: `agents` is a session the dashboard has classified from
the hook stream, so it can say what the session is *doing*; `registry_only` is Claude Code's own
list, proving a session exists with no status behind it. Read the shape from the dashboard repo's
`docs/pages/development/http-api.md` before parsing — it documents which fields are omitted rather
than null, and why `activity` must not be read as a `status`.

**An empty answer is not evidence that nothing is running.** Check `sync_listening`, the `peers`
list and `registry_unreadable` first: a dashboard that cannot see the other machine reports it
exactly like a machine with nothing on it.

What it cannot answer is whether a session can be *attached* — no field says which terminal holds
the pty. See [[peer_messaging]] for reaching one of those sessions rather than just listing it.
