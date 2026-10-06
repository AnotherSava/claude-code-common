---
name: port-uniqueness-not-a-rule
description: port uniqueness is checked in this repo's own commit gate rather than as a convention rule, and v15 exists for the per-repo replacement instead; decided 2026-10-05
metadata:
  type: project
---

"No two use cases share a port" is not a convention rule, and the reason is reach rather than
importance. Uniqueness is a relation between claimants, while a rule answers "is this repo in that
shape now" about one repo at a time — and three of the port-claiming repos (travel, travel-map,
toolbox) have no `.claude/conventions` record and no commit gate, so no rule could reach them
whatever it said. The invariant therefore lives where the registry lives: `.claude/commit-checks.sh`
runs `ports.py check` over the committed registry at every commit here, on the `ingress-lint.py`
pattern of one shared checker several gates call.

Version 015 is a different job, and conflating the two is the thing to avoid. It does not check
uniqueness; it performs the per-repo replacement — removing a port literal from a dev script so the
number is resolved from the registry at launch — and hands the checker `ports-from-registry`, which
asks only about the repo in front of it: every launch-path literal here is a `pinned` claim this repo
owns. The registry's own consistency is never that rule's business.

A universal rule was considered and declined. `conventions/authoring.md` requires per-machine *and*
silent, and a port collision usually announces itself at the bind in the session that needed it —
the same test that declined the Windows-ACL rule. The one collision that was genuinely silent was
tailscaled holding a port no process listing shows, and that is fixed in code rather than reported
by a rule: `shared/port_probe.py` names the holder, and `deploy-dev-server.sh` clears a stale
mapping before it starts a server.
