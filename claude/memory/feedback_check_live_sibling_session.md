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
