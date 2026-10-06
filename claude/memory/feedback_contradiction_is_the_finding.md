---
name: feedback_contradiction_is_the_finding
description: When two instruments disagree about the same fact, that disagreement is the finding — test the subject directly instead of re-running the one that is lying
metadata:
  type: feedback
---

Two readings of one fact that cannot both be true is not a confusing situation to re-measure; it is the
most informative thing available, and it names the next command. Stop re-running the reporter and test
the subject.

**Why:** on 2026-10-05 a dev server failed with `EADDRINUSE` on a port that
`lsof -nP -iTCP:<port> -sTCP:LISTEN` and `netstat -an` both showed free. Those two claims cannot both
hold. Five restarts, four log reads, a `pkill` of every matching process and an `rm -rf` of the build
cache went into re-asking the instruments that were already answering wrongly. A three-line
`socket.bind()` settled it in seconds — the port was genuinely held, by a root-owned system extension an
unprivileged listing cannot see; `learnings/tailscale-serve-port-ownership.md` carries that mechanism. The
user's reaction to the fifth attempt is what redirected it.

**How to apply:** when a tool reports a state that contradicts an error, write the smallest direct test
of the disputed claim — bind the port, open the file, request the URL — before running anything else
again. Prefer it to a better version of the same instrument, since the failure mode is the instrument's
*visibility* rather than its flags. And **read the script before invoking it a second time**: five of
those attempts went through a wrapper whose source named the step that was hanging, and reading it was
never the thing tried. A negative from one instrument is a reason to check what else knows, which is also
[[feedback_read_the_evidence_you_have]]'s subject from the other side — that one is about a cause built
by inference, this one about two measurements that cannot both stand. Related:
[[feedback_not_run_is_not_pass]].
