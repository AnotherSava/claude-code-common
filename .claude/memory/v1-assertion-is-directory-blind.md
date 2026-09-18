---
name: v1-assertion-is-directory-blind
description: v1's per-item migration assertion checks that a checklist line reached some file, not which of memos/ and done/ it reached, so an open item filed as addressed passes
metadata:
  type: project
---

Version 001's Path A step 4 asserts that "every checklist line in `memos.md` appears in exactly one
file under `memos/` or `memos/done/`, matched on text". The `or` is the gap: the check is satisfied
by presence anywhere under the backlog, so an item the migration routes to the wrong one of the two
directories passes it, and a `[ ]` item filed as addressed is silently closed.

Measured in tauri-dashboard on 2026-09-18. `git show 486121d^:.claude/memos.md` has
`- [ ] 2026-09-03 03:02 — Fix the Homebrew tap…` open in the final checklist state, the string
`+- [x] 2026-09-03 03:02` appears nowhere in that file's history, and `486121d chore(memos): move
the backlog to one file per memo` is the commit that added it at its `done/` path. Its body ends
"nobody has run `brew install --cask` from a clean Mac… Do that from AIR before checking this off",
so the outstanding verification is invisible in a backlog that lists only open memos.

The failure is in what the assertion reads rather than in whether a program does the reading, which
is the separate question [[adoption-prose-over-scripts]] settles. A text match against the item's
line cannot see the `[x]`, because the marker is not part of the text being matched — so the check
and the routing decision consult different things, and nothing compares them.

Version 001 is frozen and adopted, so this is not an edit to it. What it argues for is a later
version, and the intermediate state authoring.md requires for one demonstrably exists.
