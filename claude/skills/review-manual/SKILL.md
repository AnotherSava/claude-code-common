---
name: review-manual
description: >-
  Run a read-only review of the current change through the saved `review-auto` workflow, show its findings as a table
  the user ticks, then fix exactly what they ticked, following their per-row feedback.
  TRIGGER when: the user runs /review-manual, or asks for a read-only review where they choose what gets fixed.
  DO NOT TRIGGER when: the user wants the review to fix what it finds on its own — that is `review-auto` in its
  default fix mode.
---

# Review manual

The read-only review loop: the workflow reviews and verifies without editing anything, the user picks what to fix,
and this session fixes it. The user's choice and the feedback typed against a row are the instruction; the
workflow's own triage is only the pre-ticked recommendation.

## Context

- Commit gate script: !`test -f .claude/commit-checks.sh && echo PRESENT || echo MISSING`
- Scratch file ignored: !`git check-ignore -q tmp/review-findings.json && echo IGNORED || echo NOT-IGNORED`

## Steps

1. **Build the workflow's args from the conversation** as `~/.claude/skills/shared/review-auto-args.md` describes,
   with `fix: false`. **Commit gate script** in Context says whether `.claude/commit-checks.sh` is the gate.
2. **Run** `Workflow({name: "review-auto", args})` and wait for its completion notification.
3. **Present the triage** as the workflow's returned `note` says.
4. **Write the picker's rows** to `tmp/review-findings.json` when **Scratch file ignored** is `IGNORED`; otherwise
   tell the user the file would be committable and ask where it should go. The file is
   `{"title", "rows": [{"id", "finding", "rating", "view", "fix", "wording"}]}`, one row per triage row, ranked by
   your concern: `id` is the triage id, `rating` its frequency and cost, `view` your recommendation and its reason in
   one line, `fix` true where you recommend acting on it, and `wording` true where the fix would change only wording
   or documentation, which the picker draws in lighter grey.
5. **Run the picker in the background** — `python3 ~/.claude/scripts/review_picker.py tmp/review-findings.json`
   (`python` on Windows), with `run_in_background` — and wait for it to exit. Inside agterm it blocks until the user answers.
   - Exit 0 prints `{"outcome": "submitted", "fix": [ids], "feedback": {id: text}}`. An empty `fix` is an answer:
     fix nothing.
   - Exit 4 (not inside agterm) prints `{"outcome": "published", "url": ...}` at once: hand over that URL as a link
     and ask the user to tick, press **Copy answer**, and paste the result here. The pasted
     `{"fix": [ids], "feedback": {id: text}}` is the answer exactly as exit 0's would be.
   - Exit 2 (closed without Apply) or 3 (not inside agterm, and the page could not be published): show the same rows
     as a table in chat and ask which to fix and how.
   - Exit 1: report its stderr and fall back to the chat table.
6. **Fix exactly the chosen ids**, following each one's feedback where it has some. Add or update tests wherever
   behaviour changed, then run the gate from step 1 and judge it by its exit status.
7. **When the tree changed**, say so and stop: the bookmark the review recorded no longer matches, so run
   `/review-manual` again before committing.
8. **When nothing was ticked, the tree is unchanged and the workflow's `bookmark` says it was recorded, commit
   exactly the reviewed tree**, so the bookmark moves now and whatever a later `/commit` adds — its reflection,
   clean-code and docs fixes — goes into later commits that the next review picks up. This is deliberately not
   `/commit`: its sub-steps edit files, and an edit before this commit would cost another review round. An
   unrecorded bookmark has nothing to move: report why it was not recorded and leave committing to `/commit`.
   1. Run `git status --short` now, since the tree at skill load predates the review. Plan one or more commits per
      `~/.claude/skills/shared/commit-message-rules.md`, together holding every path it lists and nothing else, and
      run `python3 ~/.claude/scripts/check-commit-message.py --file <message file>` on each message.
   2. Run `python3 ~/.claude/scripts/scan-commit-confidentiality.py <every path> --range 'HEAD --not --remotes'`
      and triage its output as `/commit` step 5 describes, reading the exit code. A finding that needs an edit
      means stopping here: the edit changes the reviewed tree.
   3. Show the plan with each full message and ask for a yes. On it, run `git reset HEAD --quiet`, stage each
      commit's paths by name, and commit with `git commit -S`.
   4. Run `python3 ~/.claude/scripts/review_scope.py advance` and report its line.
   5. Report the commits, and that a later `/commit` reviews them, adds its own fixes as new commits and offers the
      push.

## Out of scope

- Do NOT fix a finding the user left unticked, however clearly it looks right.
- Do NOT run `review-auto` in fix mode, or an inline review workflow in its place.
- Do NOT commit a tree the review did not cover, amend a commit, or push; the push is `/commit`'s.
