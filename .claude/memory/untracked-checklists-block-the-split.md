---
name: untracked-checklists-block-the-split
description: chrome-assistant and intellij-jsonl-extension hold an uncommitted .claude/memos.md, so 001's split there destroys every marker with nothing able to recover them
metadata:
  type: project
---

Two repos that adopt conventions hold a `.claude/memos.md` git has never seen — chrome-assistant
and intellij-jsonl-extension, measured 2026-09-18 with
`git -C <repo> ls-files --error-unmatch .claude/memos.md`. A third untracked copy sits in
`external/agwinterm`, a third-party clone that adopts nothing.

Version 001's split deletes that file. Where it was never committed, the `[x]`/`[ ]` markers then
exist nowhere: no revision carries them, and the only copy was the one the splitting session read
minutes earlier. Version 010 exists to re-check that routing and cannot, so it has to stop and ask
there rather than concluding the repo never kept a backlog — and the silence it reads is
indistinguishable from that conclusion, which is why [[v1-assertion-is-directory-blind]]'s failure
can recur unreported.

**Commit `.claude/memos.md` in those two repos before running `/adopt` there.** One commit, before
the walk starts, and the whole problem is gone. v010's step 1 says so, but a walk reaches that
instruction only after 001 has already run and deleted the file, so the prevention has to happen
earlier than the version that documents it — which means from here, or from a session working in
that repo.
