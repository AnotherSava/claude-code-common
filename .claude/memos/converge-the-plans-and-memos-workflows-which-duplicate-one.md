---
created: 2026-10-01 19:24:11
---

# Converge the plans and memos workflows, which duplicate one mechanism

Raised 2026-10-01: do we need `docs/plans/` and `plan-archive.py` at all, now that memos exist — could plans just live in the memo folders?

**Oleg's position: the two will merge eventually.** So the near-term step below should be taken in a way that makes a later merge cheap rather than entrenching two namespaces.

**What the measurement says today.** Both systems are in active concurrent use in the same repos, days apart, which is why this is a convergence task and not a deletion:

| repo (Oleg's own) | plan files | last plan commit | last memo commit |
|---|---|---|---|
| printlab | 6 | 2026-09-28 | 2026-09-29 |
| what-is-next | 5 | 2026-09-24 | 2026-09-25 |
| tauri-dashboard | 20 | 2026-08-31 | 2026-10-01 |
| bga-assistant | 23 | 2026-05-27 | 2026-09-27 |
| chrome-assistant | 11 | 2026-04-09 | never |
| claude (dotfiles) | 1 | 2026-05-16 | 2026-10-01 |

Count only repos whose `origin` is AnotherSava. Two traps caught while gathering this: `agterm` is `umputun/agterm`, someone else's repo, and its 61 archived plans are not Oleg's — quoting them made plans look far more used than they are. `agwinterm` is a fork of `yeroo/agwinterm`; its 14 open plans against 6 archived are not evidence that archival is lagging here.

**The duplication, which is the actual target.** Both are one markdown file per item, in a committed directory, with a sibling subdirectory meaning addressed, kept forever. Implemented twice:

- memos — `.claude/memos/` + `done/`, mechanics in `memos.py`, listed newest-first by a positional index
- plans — `docs/plans/` + `completed/`, filed by `plan-archive.py start`, archived by `/commit` step 6, filename slug validated by `/commit` step 7

One shared helper behind both, with the namespaces as a parameter, is the step that shrinks this without deciding the merge.

**What a merge has to answer**, and what nearly made the case for keeping them apart:

- They mean opposite things. A memo is work deliberately *not* being done; a plan is the approved design for work in flight. A merged list offered by number in the status bar would mix the two.
- `plan-archive.py start` is the only thing that retains `ExitPlanMode` text, which otherwise lives only in the transcript. Memos have no equivalent because capture requires an offer and a yes. A merge must keep an automatic-capture path.
- The archived plans are a design log — 53 across Oleg's repos — read differently from `memos/done/`.

Two arguments *not* to lean on, both withdrawn on 2026-10-01 after Oleg corrected them: `/pr-create` and `/pr-prepare` do read `docs/plans`, but neither has been used lately, so that is not a live dependency; and the `agwinterm` archival backlog above is a fork's.
