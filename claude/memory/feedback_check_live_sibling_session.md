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
compact header arrived in the tauri-dashboard session:

1. Grep the dashboard's own `widget.jsonl` (in its app-data dir) for the target
   repo's chat_id and read the last few lines. A recent `classify` line carries
   a timestamp and that turn's closing message, so it shows both *whether* an
   agent is active there and *what* it just did — the tool reporting on its own
   siblings. See [[debug_state_transitions_via_widget_jsonl]].
2. `git -C <repo> status --short` — uncommitted and untracked files show what it
   is mid-flight on.

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
