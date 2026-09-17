---
name: pull
description: Bring this branch up to date with its upstream — fetch, judge whether the local edits collide with the incoming commits, move aside only what must move, fast-forward, and resolve what the restore turns up.
disable-model-invocation: true
allowed-tools: AskUserQuestion, Read, Grep, Bash(git fetch:*), Bash(git rev-parse:*), Bash(git rev-list:*), Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git show:*), Bash(git ls-files:*), Bash(git cat-file:*), Bash(git stash:*), Bash(git merge:*), Bash(git add:*), Bash(git reset:*)
---

# Pull remote changes

Sync this branch with its upstream and settle whatever the sync turns up. A dirty tree is the normal case here, not an error — these repos are worked from two machines and often by several concurrent sessions — so the job is to move aside as little as possible, fast-forward, and put it back.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

The reference for every branch below is `~/.claude/learnings/git-stash-pull-safety.md`: it carries the recipes, the verification baselines, and the failure modes that produce no conflict at all. This file is the decision procedure, that one is the depth. Follow its section when a step names it rather than re-deriving a recipe it already holds.

## Context
- Fetch: !`git fetch -q 2>&1 || echo FETCH-FAILED`
- Upstream: !`git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo NO-UPSTREAM`
- Incoming files: !`git diff --name-status HEAD @{upstream} 2>/dev/null || echo NONE`
- Working tree status: !`git status --short`
- Local changes vs HEAD: !`git diff --name-only HEAD`

## Process

1. **Measure the divergence, then settle the preconditions before touching anything.** Two inputs cannot come from the Context section above: a `!` line whose command carries a revision range against `@{upstream}` is handed back to be run rather than preprocessed, while the same ref as a bare argument preprocesses fine — see `~/.claude/learnings/skill-context-evaluator.md`. Run both now, one per Bash call, and refer to their output by the names given here:
   ```
   git rev-list --left-right --count @{upstream}...HEAD 2>/dev/null || echo NO-UPSTREAM
   git log --oneline -n 40 HEAD..@{upstream} 2>/dev/null || echo NONE
   ```
   The first is **Behind and ahead counts**, the second **Incoming commits**. Then stop wherever one of these holds:
   - **Upstream** is `NO-UPSTREAM` — this branch tracks nothing. Say so and stop.
   - **Fetch** is `FETCH-FAILED` — report its text verbatim and stop, because every count below is then stale.
   - **Behind and ahead counts** reads `0` on the left — already current. Say so and stop. Do not stash, merge, or touch the tree to confirm it.

2. **Read the reference before acting.** Normally that is `~/.claude/learnings/git-stash-pull-safety.md` through the Read tool. When the repo being pulled *is* the dotfiles repo — it has `claude/learnings/` at its root — read the upstream copy instead, `git show @{upstream}:claude/learnings/git-stash-pull-safety.md`, because a behind checkout's documentation is behind by the same commits and this pull is what would fix it.

3. **Classify the divergence** from **Behind and ahead counts** (left is behind, right is ahead).
   - Behind only — the fast-forward path. Continue to step 4.
   - Both non-zero — the branch has diverged and wants a rebase, which is not this skill's to run unasked. Show the incoming commits and the local ones and ask how to proceed. Stop on a no.

4. **Work out what actually has to move.** Intersect the paths in **Local changes vs HEAD** with the paths in **Incoming files**. Git's refusal to fast-forward is per-path, so only the overlap is in the way.
   - Empty intersection — stash nothing at all and go to step 6. This is the safer path, not merely the shorter one: another live session may be mid-edit in those files, and a stash/pop lifts them off disk and back seconds later.
   - Non-empty — stash exactly those paths in step 5, never the whole tree. Everything outside the overlap stays where it is.
   - Check the untracked entries (`??` in **Working tree status**) against the `A` rows of **Incoming files**. An incoming commit adding a path that already exists untracked blocks the merge and is not covered by a stash; surface the collision and ask before moving that file.
   - Before stashing, flag any overlapping file that the reference treats specially, and follow its section instead of the plain recipe: a file that is one enormous line (minified, single-line JSON, unwrapped prose) has no line granularity and must be re-applied rather than popped; a file the local side *deletes* while upstream modified it must be reconciled by content, because the modify/delete conflict resolves cleanly while silently discarding upstream's addition.
   - If **Incoming commits** shows 40 entries the list was capped there; say so before reasoning about completeness.

5. **Stash only the paths step 4 named.**
   ```
   git stash push -m "pre-pull local work" -- <paths>
   ```
   Then record the baseline, which makes a later drop reversible and is what step 8 verifies against:
   ```
   git rev-parse stash@{0}
   ```

6. **Fast-forward.**
   ```
   git merge --ff-only @{upstream}
   ```
   A refusal here means step 4's intersection was wrong. Read the error and redo step 4 — never force, and never fall back to a merge commit.

7. **Restore, keeping the staged/unstaged split.**
   ```
   git stash pop --index
   ```
   Always `--index`: a plain pop flattens the split, destroying real information whenever the index held something deliberate. A conflicted pop **keeps** the stash entry, so resolve first, then `git add` the resolved paths, then `git reset -q` to return to an all-unstaged tree, and only then `git stash drop`.

   With more than one conflict, triage the whole set before reading any of them — the reference's `awk` one-liner tags each half's headings, separating the mechanical both-appended case from two sides that rewrote the same material.

8. **Verify, including the things that never conflict.** A clean merge is not evidence; these three checks are.
   - Against the step 5 baseline, `git diff <stash-sha> -- .` should list exactly the incoming files, plus untracked files and any dirty paths deliberately left unstashed. Anything else is a local edit the merge mangled.
   - For any document that merged, list its headings and read for two that mean the same thing. Two sessions adding the same knowledge in different places produces no conflict at all.
   - Read the `A` rows of **Incoming files** against the existing filenames on the same subject — a pull that adds a file duplicating one already in the tree passes every other check.

9. **Report**: how many commits came in and what they were, what moved aside and came back, what conflicted and how it was resolved, and anything left for the user to decide.

## Out of scope
- Do NOT commit or push — that is `/commit`
- Do NOT rebase a diverged branch without explicit approval; propose it and wait
- Do NOT use `git pull --rebase --autostash` — its internal pop does not restore the index
- Do NOT use `git checkout -- .` or any bare discard; the tree is dirty by premise
- Do NOT drop a stash before step 8's checks pass
