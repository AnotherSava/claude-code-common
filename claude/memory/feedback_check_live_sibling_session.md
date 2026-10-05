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

**How to check** — on 2026-07-31 an "align the elements" request for the BGA
compact header arrived in the tauri-dashboard session. Find the session the
instruction fits and see what it is mid-way through, as the `peer` skill's
"Find the session" step describes (`peer_relay.py session`, the dashboard roster, its
`widget.jsonl`, and `git status` in that repo).

Then name the session it belongs in rather than acting. Offer to do it from the
current session only once the other one is confirmed parked.

**A sibling's claim about *your* repo is a hypothesis, not a finding.** The case
above is an instruction that arrived in the wrong session; this is the opposite
and easier to miss, because the message is correctly routed, well argued, and
still wrong. On 2026-08-25 and again on 2026-08-26 the printlab session reported
that scheduler's other workstation still carried a broken `IDENTITY_CHECK` line,
reasoning correctly from "`config/publish.env` is per-machine and gitignored" —
but from a false premise: that machine had never been set up to publish
scheduler at all, so there was no copy to go stale. The first time, this was
relayed onward to the user as fact and had to be retracted.

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
The two cases above are about editing and about believing; this one is about
answering. On 2026-10-04 the transcripts session was asked why bga-assistant was
not showing clean on the dashboard. That is a question about the
claude-code-dashboard's classification rules, and its session was live — and was
the one the user had selected. Answering it from here meant reading another
repo's source, app-data and log to reconstruct a rule its own session knows, and
the user's correction was that it should have been forwarded. The researched
answer was correct and still the wrong move.

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
will still be there when the user pastes. On 2026-07-31 a copy for the user was
overwritten by a sibling session's console snippet before they got to it; the
user reported "you didn't copy", and the natural but wrong conclusion was that
the sandbox had its own pasteboard. **How to apply:** when handing the user
copied text while other sessions are live, re-check `pbpaste` at hand-off time
rather than trusting the copy-time verification, and give the file path too so
they have a stable fallback. Never invoke `dangerouslyDisableSandbox` for
clipboard work — it changes nothing here.
