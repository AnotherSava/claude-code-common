---
name: pull
description: Bring this branch up to date with its upstream when the tree may be dirty — fast-forward, moving aside only local edits that collide. TRIGGER when: asked to pull or sync, or a session on the other machine asks for it after a push. DO NOT TRIGGER for a diverged branch or for committing.
allowed-tools: AskUserQuestion, Read, Grep, Bash(git fetch:*), Bash(git rev-parse:*), Bash(git rev-list:*), Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git show:*), Bash(git ls-files:*), Bash(git cat-file:*), Bash(git stash:*), Bash(git merge:*), Bash(git add:*), Bash(git reset:*), Bash(python3 ~/.claude/skills/shared/session_clean.py:*), Bash(python ~/.claude/skills/shared/session_clean.py:*)
---

# Pull remote changes

Sync this branch with its upstream and settle whatever the sync turns up. A dirty tree is the normal case here, not an error — these repos are worked from two machines and often by several concurrent sessions — so the job is to move aside as little as possible, fast-forward, and put it back.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

The reference for every branch below is `~/.claude/learnings/git-stash-pull-safety.md`: it carries the recipes, the verification baselines, and the failure modes that produce no conflict at all. This file is the decision procedure, that one is the depth. Follow its section when a step names it rather than re-deriving a recipe it already holds.

**When a message asked for this run** — `/commit` on the other machine sends one after each push — the message is a claim, but this skill re-measures its premise in step 1: if nothing is inbound, say so and stop. Send no reply unless something needs the sender's attention; the `peer` skill covers anything the message asks beyond the pull.

## Context
- Fetch: !`git fetch -q 2>&1 || echo FETCH-FAILED`
- Upstream: !`git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo NO-UPSTREAM`
- Working tree status: !`git status --short`
- Local changes vs HEAD: !`git diff --name-only HEAD`

## Process

1. **Measure the divergence, then settle the preconditions before touching anything.** Three inputs cannot come from the Context section above, for two separate reasons, and both are recorded in `~/.claude/learnings/skill-context-evaluator.md`. A `!` line whose command carries a revision range against `@{upstream}` is handed back to be run rather than preprocessed, while the same ref as a bare argument preprocesses fine. Worse, `!` lines are not evaluated in the order they are written, so any of them reading `@{upstream}` may see the ref as it stood *before* the Fetch line updated it. Nothing above is safe to read about the remote; a process step is, because every `!` line has finished by the time one runs. So run all three here, one per Bash call, and refer to their output by the names given:
   ```
   git rev-list --left-right --count @{upstream}...HEAD 2>/dev/null || echo NO-UPSTREAM
   git log --oneline -n 40 HEAD..@{upstream} 2>/dev/null || echo NONE
   git diff --name-status HEAD @{upstream} 2>/dev/null || echo NONE
   ```
   In order they are **Behind and ahead counts**, **Incoming commits** and **Incoming files**. Then stop wherever one of these holds:
   - **Upstream** is `NO-UPSTREAM` — this branch tracks nothing. Say so, signal per step 10, and stop.
   - **Fetch** is `FETCH-FAILED` — report its text verbatim and stop, because every count below is then stale. Do not signal: an unmeasured remote is a real thing to come back to.
   - **Behind and ahead counts** reads `0` on the left — already current. Say so, signal per step 10, and stop. Do not stash, merge, or touch the tree to confirm it.

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

10. **Say that this run left nothing to come back to**, where that is true, so the dashboard can rest the row instead of showing it as holding work:
    ```
    python3 ~/.claude/skills/shared/session_clean.py
    ```
    Use `python` on Windows. Run it when step 9's last two clauses are both empty — nothing conflicted and nothing is left for the user — or at whichever step 1 stop sent you here. Do **not** run it after a conflict you resolved, a question you put to the user, or `FETCH-FAILED`; each of those is something to return to.

    Do not condition it on how the turn started, and do not condition it on what the row looked like beforehand. Both are the dashboard's to test and it holds the evidence for each: it recognises a relayed request by the preamble it minted itself, and it knows what the row was before this turn opened. Report what this run did and let it weigh the rest. The command prints nothing and always exits 0, including where no dashboard is listening — an absent signal is read as "not clean", which is the safe direction. A later prompt revokes a signal whose turn never settled, so a pull followed by real work needs nothing undone here.

## Out of scope
- Do NOT commit or push — that is `/commit`
- Do NOT rebase a diverged branch without explicit approval; propose it and wait
- Do NOT use `git pull --rebase --autostash` — its internal pop does not restore the index
- Do NOT use `git checkout -- .` or any bare discard; the tree is dirty by premise
- Do NOT drop a stash before step 8's checks pass
