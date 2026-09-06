---
name: wrap-up
description: >-
  Close out a section of work. Reviews the current session's transcript for questions
  you never answered, concerns you passed over, ideas worth memoing, and follow-ups
  Claude promised but never delivered; settles each one with you, then runs /commit and
  hands over to /clear.
  TRIGGER when: the user runs /wrap-up, or says they are ready to finalize, close out,
  or wrap up the current section of work.
  DO NOT TRIGGER when: the user only wants to commit (use /commit), to park a single
  idea (/memo), or to persist durable knowledge (/reflect).
allowed-tools: Bash(python3 ~/.claude/skills/wrap-up/scripts/session_scan.py:*), Bash(python3 ~/.claude/skills/memo/memos.py:*), Bash(git rev-parse:*), Bash(git status:*), Bash(git log:*), Read, Edit, Write, Glob, Grep, Skill
---

# Wrap Up

Review everything said in this session for business left unfinished, settle each item with
the user, then commit, push, and hand over to `/clear`.

The review exists because the end of a stretch of work is where things quietly go missing:
a question asked while the user was reading something else, a concern raised in passing, an
idea worth keeping, a check promised and never run. A commit will not surface any of it, and
neither will a context that has been compacted. The transcript on disk still holds all of it.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Uncommitted changes: !`git status --short`
- Pending memos: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && cat "$R/.claude/memos.md" 2>/dev/null | grep '^- \[ \]' || echo "(none)"`
- Session digest: !`python3 ~/.claude/skills/wrap-up/scripts/session_scan.py`

## Working directory

The memo file is `<Repo root>/.claude/memos.md`. The `memos.py` helper resolves that path
itself, so it works from any subdirectory; every other path in this skill is relative to
**Repo root**, which may differ from the current directory.

## Process

### 1. Confirm the digest is real

Read the `=== session ===` header of **Session digest** before trusting a word of the body.

- `resolved-via: session-id` is the good case: the digest is this session, start to finish.
- `resolved-via: newest-in-cwd-dir` means the session id was unavailable and the most recently
  written transcript for this directory was used instead. That is probably this session and
  might be a different one. Say so before presenting anything drawn from it.
- `resolved-via: UNRESOLVED` means there is no transcript to review. Say that plainly and skip
  to step 7. Do **not** reconstruct the session from your own context and present the result as
  a transcript review: the whole point of reading the file is that your context may have lost
  what the file kept, so a review built from memory is the one thing this skill must not fake.
- `window: whole transcript` is the normal case: the file already began at a `/clear`, so the
  digest is one section of work. `window: clipped to the last /clear` means the file also held
  earlier work and the digest starts at the boundary instead, which is still one section.
- `opened-with-clear: no` means no `/clear` appears anywhere in the file, so the window may span
  more than one section of work (a resumed or continued session). Mention it, then review it all.
- A `reductions:` line other than `none` means long messages were shortened to fit the budget.
  No message was dropped, but a quotation may have an elision in the middle.

### 2. Read the whole conversation

The `=== conversation ===` block is every word both sides said, in order, with tool traffic
collapsed to one line per turn. Blocks marked `USER decided` are answers given through a
question prompt rather than typed as a message; they routinely carry direction that appears
nowhere else in the transcript. Thinking is not stored in transcripts at all, so a concern
that was never actually said out loud cannot be reviewed here.

Read it in full before judging anything, and prefer it to your own recollection of the session.
Where the two disagree, the transcript is right.

### 3. Collect candidates in four categories

Be generous here and filter in step 4. Gather:

**a. Questions never answered.** Anything you asked that the user's next message did not
address: they replied about something else, answered one part of a two-part question, or picked
an option while ignoring the follow-up attached to it. Skip rhetorical questions, questions you
went on to answer yourself, and questions the subsequent work settled beyond doubt.

**b. Concerns passed over.** A risk, defect, trade-off, or objection you raised that no decision
ever met: a recommendation neither accepted nor rejected, a defect noticed in passing and
reported but not fixed, a limitation stated once and never revisited. A concern the user
explicitly overruled is a decision, not an open item; leave it alone.

**c. Memo-worthy asides.** Ideas for other work that either side raised and nobody captured.
The global rule is to offer a memo when the user drops one of these; this is the backstop for
the times that offer was never made.

**d. Promises not kept.** Things you said you would do, check, or come back to and never did,
plus verification you said was skipped, deferred, or impossible ("I could not reproduce this",
"the tests were not run", "I will confirm once the build finishes"). This category is the one
the transcript is uniquely good at, because these lines are exactly what a compaction discards.

### 4. Filter to what is still live

Test every candidate against the current state of the repository, not just against the
transcript, and **verify instead of assuming**. Reading a file or grepping for a symbol takes
seconds and is a great deal cheaper than making the user dismiss an item that was already
handled. Drop a candidate when:

- the working tree already answers it (check **Uncommitted changes**, then read the file)
- a later message in the digest settled it, even indirectly
- it is already in **Pending memos**
- the approach changed underneath it, so the question no longer means anything
- a later step of this skill already owns it: `/commit` runs the remote sync check, `/reflect`,
  `/clean-code`, `/documentation` and the confidentiality scan, so none of those is ever a
  finding here, however live it looks in the transcript
- an earlier `/wrap-up` in this same session already disposed of it

That last one needs no bookkeeping: a previous run of this skill is itself in the transcript,
along with the user's dispositions, so anything settled there reads as settled. Treat those
decisions as final and never re-raise them.

If nothing survives the filter, say so in one line and go to step 7. Do not manufacture
findings to justify the review; a skill that always finds something is one the user learns to
skim.

### 5. Present the findings

Number the items in one continuous sequence, grouped under the four category headings, with
the strongest first inside each group. For each item give a short bold title, the quoted words
with their `[N] HH:MM` reference from the digest, one line on why it is still open, and a
recommended disposition.

```
**Concerns passed over**

3. **The publish path was never re-tested after the rename**
   [14] 16:02 "I have not re-run publish since renaming the container, so this is unverified."
   Still open: nothing in the session ran it afterwards, and the rename is in the pending diff.
   Recommend: answer now (one command, and the commit depends on it).
```

Close with the disposition prompt, exactly three choices:

```
Reply `recommended` to take every suggestion as marked, or override per item:
`answer 2`, `memo 3 5`, `drop 1`. Anything you do not name keeps its recommendation.
```

Then stop and wait. This is a gate: nothing is committed until the list is disposed of.

### 6. Apply the dispositions

- **answer** is ordinary work. Do it now, in full, and let the resulting changes flow into the
  commit in step 7. If the answer settles a decision without changing any code, leave recording
  it to `/reflect`, which step 7 runs anyway.
- **memo** appends one entry per item: `python3 ~/.claude/skills/memo/memos.py add "<text>"`.
  Write each one to stand on its own, naming the thing and the concrete next step. The session
  it came from is about to be cleared, so a memo that only gestures at the conversation
  ("fix the thing we discussed") will be unreadable in three weeks.
- **drop** means do nothing at all: no memo, no work, no argument, no raising it again later in
  the same run.

Report what you did in one short line per item, then continue to step 7 in the same response.

### 7. Commit

Run `/commit`. It owns the rest: the remote sync check, `/reflect` for durable knowledge,
`/clean-code`, `/documentation`, the confidentiality scan, the commit plan, the push, and the
closing memo list. Honor its gates, and do not duplicate its work here. In particular, leave
the remote alone: syncing a branch whose tree is dirty has a specific safe order that `/commit`
step 1 already encodes, and doing it early here would only get it wrong differently.

If the tree is clean and step 6 changed nothing, there may be nothing to commit. Run `/commit`
anyway: reflection can produce files worth committing, and that skill stops on its own if the
tree is still clean afterwards.

### 8. Hand over to `/clear`

Once the push is confirmed, close with a single line telling the user to run `/clear`, and say
what it buys: the next transcript begins at that point, which is what keeps a future `/wrap-up`
scoped to exactly one section of work.

This skill cannot run it. Clearing the context is a built-in CLI command, not a skill or a
tool, so the user has to type it. Recommend it, do not claim to have done it, and do not
recommend it at all if the user declined the push in step 7, since clearing on top of unpushed
work throws away the context needed to finish it.

## Out of scope

- Do NOT act on an item the user marked memo or drop.
- Do NOT re-raise anything an earlier `/wrap-up` in this session already settled.
- Do NOT read another session's transcript, or files under `~/.claude/projects/` by hand; the
  digest is the only session source this skill uses.
- Do NOT do `/reflect`'s job. It captures durable knowledge; this skill captures unfinished
  business. Both run, and they do not overlap.
- Do NOT claim to have cleared the context.

## Important

- The gate in step 5 is the skill. Committing before the user has disposed of the findings
  defeats the reason for looking at all.
- Present a finding only after checking it is still live. An item the user has to dismiss
  because a file already answers it costs more trust than the item was worth.
- Quote the user and yourself accurately from the digest, with the reference so either can be
  located. Do not paraphrase a concern into something sharper than what was actually said.
- The `allowed-tools` list above deliberately covers only this skill's own machinery. Answering
  a finding in step 6 is arbitrary work and goes through the normal permission flow; do not
  narrow the step to fit the list.
