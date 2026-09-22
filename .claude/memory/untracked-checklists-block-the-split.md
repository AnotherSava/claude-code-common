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

**A tracked checklist with an uncommitted edit loses only that edit, and loses it the same way.**
url-cleaner and printlab are both in that state as this is written — `git status --short` shows
` M .claude/memos.md` — and 001 splits from the file on disk while nothing afterwards can read
anything but a committed revision. So the item captured since the last commit reaches a memo file
whose marker is unrecoverable, and the memo reads as an ordinary new capture rather than as one
whose state nobody can now establish.

**A session writing a memo into another repo creates this state itself.** printlab's dirty line was
appended from a session working in the dotfiles repo on 2026-09-21, by hand, because `memos.py`
refuses below v001 and `/adopt` there was not that session's to run. Writing the capture and leaving
it uncommitted is the same hazard as finding it uncommitted — so a hand-written entry has to be
routed to the owning session for a commit, not just written and reported.

**Commit `.claude/memos.md` in all three repos before running `/adopt` there.** One commit, before
the walk starts, and the whole problem is gone. v010's step 1 says so, but a walk reaches that
instruction only after 001 has already run and deleted the file, so the prevention has to happen
earlier than the version that documents it — which means from here, or from a session working in
that repo.
