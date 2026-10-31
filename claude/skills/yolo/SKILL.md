---
name: yolo
description: Commit everything pending and push it, so it can be tested now and fully reviewed later — no review, no reflection, no questions in the normal case. Skips review-auto, /reflect, /clean-code beyond removing debug prints, and /docs-relevance; never skips the privacy scan, the project gate, the commit-message check or the signature, and stops to ask on a privacy finding, a failing gate, a diverged branch, or a file another session may still be writing. The next /wrap-up reviews what it pushed. TRIGGER when: the user runs /yolo, or asks to push work as-is to test it. DO NOT TRIGGER when: the user is closing out a piece of work (that is /wrap-up), or wants a commit without a push (a skill calls `shared/commit.py` for that).
allowed-tools: Read, Edit, Grep, Glob, ListAgents, ToolSearch, SendMessage, Bash(bash ~/.claude/skills/shared/project_memory.sh), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git fetch:*), Bash(git rev-list:*), Bash(git rev-parse:*), Bash(git show:*), Bash(git ls-files:*), Bash(gh run list:*), Bash(gh run watch:*), Bash(gh run view:*), Bash(python3 ~/.claude/skills/shared/commit.py:*), Bash(python ~/.claude/skills/shared/commit.py:*), Bash(python3 ~/.claude/skills/shared/push.py:*), Bash(python ~/.claude/skills/shared/push.py:*), Bash(python3 ~/.claude/skills/shared/gate_pushed_tree.py:*), Bash(python ~/.claude/skills/shared/gate_pushed_tree.py:*), Bash(python3 ~/.claude/scripts/review_scope.py:*), Bash(python ~/.claude/scripts/review_scope.py:*), Bash(python3 ~/.claude/skills/shared/peer_repo_changes.py:*), Bash(python ~/.claude/skills/shared/peer_repo_changes.py:*), Bash(python3 ~/.claude/skills/memo/memos.py:*), Bash(python ~/.claude/skills/memo/memos.py:*)
---

# Yolo

Commit what is pending and push it, so the work can be tested. The next `/wrap-up` reviews every commit pushed since
the last recorded review, this one's included; its `/clean-code` and `/docs-relevance` passes run over the scope
`change_scope.py` reads (README, its bullet under the shared steps), which leaves out what this run pushes. What never
waits is anything that
would publish something it should not: the privacy scan, the project gate, the message check and the signature all
run, through the same shared steps `/wrap-up` uses.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints. Use `python` in place of `python3` on
Windows throughout.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Uncommitted changes: !`git status --short`
- Recent commits: !`git log --oneline -5`
- Project memory: !`bash ~/.claude/skills/shared/project_memory.sh`

## Hard stops

The run asks nothing unless one of these happens. Each stops it before anything is pushed and puts the specific
question to the user:

- **A blocking privacy finding** from `commit.py`, of any class the docstring of
  `~/.claude/scripts/scan-commit-confidentiality.py` lists as blocking. Show the finding and ask whether it is a leak (remove it) or a
  false positive (add its `allow=` value to `.claude/confidentiality-allow` with a comment saying why).
- **A failing gate.** Show its output.
- **A branch that has diverged from its upstream.** A rebase is the user's call.
- **A path another session may still be writing** (`shared/commit-grouping.md`, the busy-peer check).

Anything else a step reports — a review finding from the scan, a debug print kept, junk left in place — goes in the
final report, not into a question.

## Process

1. **Sync** as `~/.claude/skills/shared/sync-and-push.md` describes. A diverged branch is a hard stop.

2. **Remove debug output added during the work** — `print()`, `console.log()`, `Debug.Log()` and the like, in the
   changed code only. Keep one only when this session needs it to read the result of the test it is pushing for, and
   name each one kept in the report. Nothing later removes it (see the scope above), so the session takes it out by
   hand once the test is read.

3. **Group the change set** as `~/.claude/skills/shared/commit-grouping.md` describes, `review_scope.py layout`
   included. Draft each message to a file under the repo's gitignored `tmp/`. Do not present the plan: the report
   after the push is where the user sees it.

4. **Gate the tree before committing:** `python3 ~/.claude/skills/shared/gate_pushed_tree.py --caller yolo --record`.
   A failure is a hard stop. A pass is recorded, so the push step's own gate run skips the identical tree.

5. **Commit each group:** `python3 ~/.claude/skills/shared/commit.py -F <message-file> [--reviewed] <paths…>`, one
   call per group, in order. Exit 1 is a refusal: a blocking privacy finding is a hard stop, and any other refusal
   (a message the checker rejects, a path with no change) is yours to fix and retry. Its review findings come with
   their own instruction in its output. Then run `python3 ~/.claude/scripts/review_scope.py advance`.

6. **Push:** `python3 ~/.claude/skills/shared/push.py --caller yolo`. It gates the published state (skipping a tree
   step 4 passed), pushes, publishes the review bookmark, asks the other machine to pull, lists CI runs when the
   repo has workflows, and ends on the bookmark's status line.

7. **Watch CI and hand off other repos** as the "After the push" section of `shared/sync-and-push.md` describes.

## Report

One short block: the commits made (hash and subject), anything left out of them and why, debug prints kept, review
findings from the scan with your one-line reading of each, and the push step's lines as it printed them, its status
line last.

## Out of scope

- Do NOT run review-auto, `/reflect`, `/clean-code`, `/docs-relevance` or `/screenshot-relevance`; that is `/wrap-up`.
- Do NOT run `git add`, `git commit` or `git push` directly; `commit.py` and `push.py` carry the checks.
- Do NOT move a finished plan, close a memo the change set does not deliver, or rebase a diverged branch.
