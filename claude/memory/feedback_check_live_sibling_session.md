---
name: check-for-live-sibling-session
description: An instruction that doesn't fit the current repo probably belongs to another live session — check before editing that repo's files
metadata:
  type: feedback
---

Several Claude sessions run at once (that is what the claude-code-dashboard
exists to track), so an instruction sometimes arrives in the wrong one. The
tell: it reads as a non-sequitur for the current repo and matches work
happening elsewhere.

**Why it matters:** the sibling session usually has uncommitted changes.
Editing those files from a second session risks clobbering work in flight, and
you have none of the context the other session built up.

**How to check** — find the session the instruction fits and see what it is
mid-way through, as the `peer` skill's "Find the session" step and its "What a
session is doing right now" paragraph describe.

Then name the session it belongs in rather than acting. Offer to do it from the
current session only once the other one is confirmed parked.

**A sibling's claim about *your* repo is a hypothesis, not a finding.** A
misrouted instruction is one failure; this is the opposite and easier to miss,
because the message is correctly routed, well argued, and still wrong: a claim
that a per-machine, gitignored file on the other machine is stale can reason
correctly from a false premise, such as that file never having been set up
there. Relayed onward to the user as fact, it has to be retracted.

**Why:** the sibling is reasoning about a file it cannot see. Gitignored,
per-machine and untracked files are exactly where cross-session claims go wrong,
because the only evidence available to the other session is what *ought* to be
there.

**How to apply:** verify against your own tree before acting on such a claim
*and* before repeating it — the repeating is what does the damage, since it
launders a guess into a fact. Then tell the sibling what you actually found. A
wrong shared premise stays wrong for everyone until someone checks it, and the
sibling generally wants to know: mine offered to fix anything of theirs that
broke rather than hand it back.

**A question about another project's behaviour is routed, not researched here.**
The misrouted-instruction and sibling's-claim cases are about editing and about believing; this one is about
answering. When a question is about how another project behaves and that
project's session is live, forward it there rather than reading the other repo's
source, app-data and logs to reconstruct a rule its own session knows; even a
correct researched answer is the wrong move.

**Why:** the owning session can check its own tree and act on what it finds; a
foreign session can only describe. So the research is duplicated work that ends
in a handoff anyway, and any fix it proposes arrives as a hypothesis the owner
must re-verify.

**How to apply:** when the subject of a question is another project's code or
behaviour, forward it to that project's session (the `peer` skill) before
investigating. Say in the message what prompted it, and keep the investigation
for what *this* repo can answer. Forwarding needs no approval, so the cost of
getting it wrong is one message.

**Siblings also contend for shared OS state — the clipboard especially.** All
sessions share one macOS pasteboard (sandboxed and unsandboxed Bash read the
same one; there is no per-sandbox clipboard). So a `pbcopy` followed by a
`pbpaste` roundtrip proves only that the write happened — not that the content
will still be there when the user pastes: a sibling can overwrite it first, and
the tempting wrong conclusion is that the sandbox has its own pasteboard.
**How to apply:** when handing the user copied text while other sessions are
live, re-check `pbpaste` at hand-off time rather than trusting the copy-time
verification, and give the file path too so they have a stable fallback. Never
invoke `dangerouslyDisableSandbox` for clipboard work — it changes nothing here.
