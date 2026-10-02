---
created: 2026-10-01 19:09:14
---

# A forked skill wrote into the real tree and clobbered the parent's /tmp message files

Measured 2026-10-01 during a `/commit` run. A backgrounded `/docs-relevance` fork broke two separate isolation contracts, each with its own fix.

**1. It wrote into the caller's working tree instead of handing back a patch.**

It modified `claude/skills/release/SKILL.md` at 18:50:20, after writing its patch at 18:49:12 — byte-identical content, same blob hashes, so it applied its own patch rather than leaving that to the caller. Its report then listed that same change among three things it "proposed but did not patch".

README's Docs Relevance section already states the contract: it edits a detached worktree "then hands back a unified diff for the caller to read and `git apply` … routing them through a patch keeps one writer." The rule is written and was not followed, so stating it again is not the fix — it needs enforcing. `claude/scripts/worktree-sandbox.py` creates the worktree; the question is what stops an agent inside it from addressing a path outside it.

**2. It wrote the same /tmp filenames the parent was using.**

Both sides wrote commit-message drafts to `/tmp/m1.txt` and `/tmp/m2.txt`. The fork's writes (18:52:31, 18:53:24) landed over the parent's (~18:47), so `git commit -F /tmp/m1.txt` produced commit `7253b80`: a `fix(release): quote the signing probe's glob` subject, with a body describing a glob fix, over a diff containing the `docs-relevance` step-9 rule and a README bullet. A message cannot be repaired by a later commit, so this cost a `/reset` and a re-commit (now `cb4448a` and `787e931`).

Cheap fix for this half: scratch and message files go to the repo's own `tmp/` under a per-agent name, never a bare `/tmp/<short>.txt`. The repo `tmp/` is already the documented home for agent scratch and is gitignored. Worth applying wherever a skill writes a message file — `/commit` and `/wrap-up` both do.

Why this is worth fixing rather than remembering: both failures produced output that looked correct. The stray tree write arrived as a plausible fix, and the clobbered message passed `check-commit-message.py` — it is a valid Conventional Commit, just about different code.
