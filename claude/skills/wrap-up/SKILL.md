---
name: wrap-up
description: >-
  Close out a section of work with one approval. Runs review-auto over everything since the
  last recorded review, reviews the session's transcript for unanswered questions, passed-over
  concerns, memo-worthy ideas and unkept promises, drafts what /reflect would save, groups the
  commits, then stops once on a single summary; one answer applies the dispositions, saves,
  commits and pushes. Then offers deploy, publish and release, and hands over to /clear.
  TRIGGER when: the user runs /wrap-up, or says they are ready to finalize, close out,
  or wrap up the current section of work.
  DO NOT TRIGGER when: the user wants to push work as-is to test it (use /yolo), to park a
  single idea (/memo), or to persist durable knowledge only (/reflect).
allowed-tools: Bash(python ~/.claude/skills/wrap-up/scripts/session_scan.py:*), Bash(bash ~/.claude/skills/wrap-up/scripts/ship_wrappers.sh), Bash(bash ~/.claude/skills/shared/project_memory.sh), Bash(bash ~/.claude/skills/wrap-up/scripts/release_candidates.sh), Bash(python ~/.claude/skills/memo/memos.py:*), Bash(git rev-parse:*), Bash(git status:*), Bash(git log:*), Bash(python ~/.claude/skills/shared/peer_relay.py:*), Bash(python3 ~/.claude/skills/shared/peer_relay.py:*), Bash(git fetch:*), Bash(git rev-list:*), Bash(git diff:*), Bash(git show:*), Bash(gh issue list:*), Bash(gh run list:*), Bash(gh run watch:*), Bash(gh run view:*), Bash(git apply:*), Bash(python3 ~/.claude/skills/shared/commit.py:*), Bash(python ~/.claude/skills/shared/commit.py:*), Bash(python3 ~/.claude/skills/shared/push.py:*), Bash(python ~/.claude/skills/shared/push.py:*), Bash(python3 ~/.claude/skills/shared/gate_pushed_tree.py:*), Bash(python ~/.claude/skills/shared/gate_pushed_tree.py:*), Bash(python3 ~/.claude/skills/shared/change_scope.py:*), Bash(python ~/.claude/skills/shared/change_scope.py:*), Bash(python3 ~/.claude/skills/shared/peer_repo_changes.py:*), Bash(python ~/.claude/skills/shared/peer_repo_changes.py:*), Bash(python3 ~/.claude/skills/shared/format_files.py:*), Bash(python ~/.claude/skills/shared/format_files.py:*), Bash(python3 ~/.claude/scripts/review_scope.py:*), Bash(python ~/.claude/scripts/review_scope.py:*), Bash(bash ~/.claude/scripts/audit-skill-tracking.sh), Workflow, Bash(bash scripts/deploy.sh), Bash(bash scripts/publish.sh), ListAgents, ToolSearch, SendMessage, Read, Edit, Write, Glob, Grep, Skill
---

# Wrap Up

Close out a section of work: review the change, review everything said in this session for business left
unfinished, then put all of it in front of the user **once** — the review's triage, the open items, what reflection
would save, the commit plan. One answer settles everything; after it the skill applies, commits and pushes without
asking again, then offers to run and ship what was committed, offers a release when it holds features or fixes, and
hands over to `/clear`.

The commit and the push go through the shared steps every committing skill uses — `shared/commit.py`,
`shared/push.py`, `shared/commit-grouping.md` — never through another top-level skill, so nothing here has to guess
what a nested skill already did.

The review exists because the end of a stretch of work is where things quietly go missing:
a question asked while the user was reading something else, a concern raised in passing, an
idea worth keeping, a check promised and never run. A commit will not surface any of it, and
neither will a context that has been compacted. The transcript on disk still holds all of it.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Uncommitted changes: !`git status --short`
- Pending memos: !`python ~/.claude/skills/memo/memos.py list --width 120 2>&1 || echo "(the backlog could not be read — the line above says why; it is NOT an empty backlog)"`
- Session digest: !`python ~/.claude/skills/wrap-up/scripts/session_scan.py`
- Ship wrappers: !`bash ~/.claude/skills/wrap-up/scripts/ship_wrappers.sh`
- Project memory: !`bash ~/.claude/skills/shared/project_memory.sh`

## Working directory

The memo backlog is `<Repo root>/.claude/memos/`, one file per memo. The `memos.py` helper
resolves that path itself, so it works from any subdirectory; every other path in this skill is
relative to **Repo root**, which may differ from the current directory.

## Process

### 1. Confirm the digest is real

Read the `=== session ===` header of **Session digest** before trusting a word of the body.

- `resolved-via: session-id` is the good case: the digest is this session, start to finish.
- `resolved-via: newest-in-cwd-dir` means the session id was unavailable and the most recently
  written transcript for this directory was used instead. That is probably this session and
  might be a different one. Say so before presenting anything drawn from it.
- `resolved-via: UNRESOLVED` means there is no transcript to review. Say that plainly, skip
  steps 3 to 5, and leave the summary's open-items section saying so. Do **not** reconstruct the session from your own context and present the result as
  a transcript review: the whole point of reading the file is that your context may have lost
  what the file kept, so a review built from memory is the one thing this skill must not fake.
- `window: whole transcript` is the normal case: the file already began at a `/clear`, so the
  digest is one section of work. `window: clipped to the last /clear` means the file also held
  earlier work and the digest starts at the boundary instead, which is still one section.
- `opened-with-clear: no` means no `/clear` appears anywhere in the file, so the window may span
  more than one section of work (a resumed or continued session). Mention it, then review it all.
- A `reductions:` line other than `none` means long messages were shortened to fit the budget.
  No message was dropped, but a quotation may have an elision in the middle.

### 2. Sync, then start the review

Sync as `~/.claude/skills/shared/sync-and-push.md` describes. A diverged branch goes at the top of the summary in
step 7, and a fetch failure is said there too.

Before launching it, settle what belongs in the tree, since the review snapshots every untracked file that is not
ignored and a reviewed path left out of the commits stops the bookmark from moving: delete junk such as crash dumps,
and check every path this session did not write for a peer still writing it, both as
`~/.claude/skills/shared/commit-grouping.md` describes under what belongs in the change set. A path held for a peer
goes at the top of the summary, since the review will include it.

Then launch the saved `review-auto` workflow in fix mode, building its args as
`~/.claude/skills/shared/review-auto-args.md` describes. Pass no `rounds`: the workflow runs until a round finds nothing worth
fixing, and its default cap is only a guard against a fixer and reviewers that never settle. It reviews everything since the last recorded review —
the working tree and every commit `/yolo` pushed since — and runs in the background, so do steps 3 to 5 while it
works and collect its result before step 6. Skip it only when there is nothing since the bookmark at all
(`review_scope.py status` reports 0 commits past it and the tree is clean); say so in the summary.

### 3. Read the whole conversation

The `=== conversation ===` block is every word both sides said, in order, with tool traffic
collapsed to one line per turn. Blocks marked `USER decided` are answers given through a
question prompt rather than typed as a message; they routinely carry direction that appears
nowhere else in the transcript. Thinking is not stored in transcripts at all, so a concern
that was never actually said out loud cannot be reviewed here.

Read it in full before judging anything, and prefer it to your own recollection of the session.
Where the two disagree, the transcript is right.

### 4. Collect candidates in four categories

Be generous here and filter in step 5. Gather:

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

### 5. Filter to what is still live

Test every candidate against the current state of the repository, not just against the
transcript, and **verify instead of assuming**. Reading a file or grepping for a symbol takes
seconds and is a great deal cheaper than making the user dismiss an item that was already
handled. Drop a candidate when:

- the working tree already answers it (check **Uncommitted changes**, then read the file)
- a later message in the digest settled it, even indirectly
- it is already in **Pending memos**
- the approach changed underneath it, so the question no longer means anything
- a later step of this skill already owns it: the review, the clean-up passes, reflection, the
  privacy scan, the commit and the push are never findings here, however live they look in the
  transcript
- step 9 already owns it: the change not having been run on this machine, not having been
  shipped to where its users are, and not having been released, are the offers that step makes,
  so none of them is a finding — a *failure* one of them produced during the session still is
- the other machine's own `/wrap-up` or `/yolo` will surface it — an untracked file in that machine's clone of
  this repo is in its next change set and bundled by the plan-file rule,
  so a wrap-up here adds nothing. Raised as an `answer` on 2026-09-28 (an archived plan left
  untracked on the Mac) and dropped once the user pointed at that commit.
- it is not this session's unfinished business. A true, routable observation about another repo
  — or about another machine's per-machine configuration — is not a finding here just because
  you said it once. Narrowing a concern the user has already corrected and re-presenting the
  residue reads as not having listened. Measured 2026-09-19: a note that `corepack enable npm`
  was unmeasured on the Windows box was raised as a routed ping, after the user had already
  pointed out that the repo in question is not cloned there
- an earlier `/wrap-up` in this same session already disposed of it

That last one needs no bookkeeping: a previous run of this skill is itself in the transcript,
along with the user's dispositions, so anything settled there reads as settled. Treat those
decisions as final and never re-raise them.

If nothing survives the filter, the summary's open-items section says so in one line. Do not manufacture
findings to justify the review; a skill that always finds something is one the user learns to
skim.

### 6. Prepare everything the summary needs

Nothing here asks the user anything; each sub-step's question, if it has one, becomes a line in step 7.

- **The review's result.** Collect the `review-auto` triage table: what it fixed, what it left and why, whether the
  bookmark was recorded. A recorded bookmark is what this skill exists to produce — the push it makes is of a tree a
  review passed — so an unrecorded one is never a summary line beside a commit plan:
  - **A lens that returned nothing, or a finding left unverified:** transport, not judgement. Relaunch the run with
    `Workflow({scriptPath, resumeFromRunId})` so only the dead calls run again, up to three times.
  - **The cap reached with fix-class work still found:** the fixer and the reviewers are undoing each other, since
    later rounds review only what the previous fixes changed. Stop before the summary and show the findings that keep
    returning; the user decides how to settle them. Nothing is committed or pushed until a run records the bookmark,
    unless the user answers `hold` (commit, no push) or asks for `/yolo`.
  - **A fix round's gate that failed:** report the gate's output and stop, as for a failing gate below.
- **Reflection, drafted.** Invoke `/reflect` with the argument `draft`: it saves its research findings directly
  and returns the feedback-derived ones and any scope promotions as a list instead of asking. Those go in the summary.
- **Clean-up passes.** Run `python3 ~/.claude/skills/shared/change_scope.py` and honour its verdicts:
  `SKIP` when `review-auto` polished this tree. On `RUN`, run `/clean-code`, `/docs-relevance` and
  `/screenshot-relevance` as that verdict says; a change any of them would make only with approval becomes a summary
  line rather than a pause. The last two are backgrounded forks that hand back a patch: collect, read and apply each
  as the "For the caller" section of `~/.claude/skills/shared/forked-sandbox.md` says, before drawing the commit plan.
  A capture one reports as pending is a summary line too, run after the answer.
- **Untracked skills.** `bash ~/.claude/scripts/audit-skill-tracking.sh`; each path it lists is a summary line asking
  keep (un-ignore it) or local (record it in `claude/untracked-skills.local.txt`).
- **Open issues.** `gh issue list --state open --limit 30`; an issue the change set bears on is a summary line asking
  whether to address it. Unrelated issues are listed after the push, one line each.
- **The commit plan.** Group the change set as `~/.claude/skills/shared/commit-grouping.md` describes,
  `review_scope.py layout` included, and draft each message to a file under the repo's gitignored `tmp/`. Format each
  commit's file list with `python3 ~/.claude/skills/shared/format_files.py`.
- **The gate.** `python3 ~/.claude/skills/shared/gate_pushed_tree.py --caller wrap-up --record`. A failure is not a
  summary line: report it and stop, since there is nothing to approve over code that fails its own checks.

### 7. Present one summary

One message, in this order, under these headings. The headings carry no numbers: the items under them are numbered in
one continuous sequence so any of them can be overridden by number, and a numbered heading above numbered items reads
as two clashing lists.

- **Review** — the triage table as the workflow returned it, and whether the bookmark was recorded.
- **Open items** — the findings from step 5, grouped under the four category headings, the strongest first inside
  each group.
- **To save** — what `/reflect` drafted, each with its destination.
- **To decide** — clean-up proposals, untracked skills, related issues, finished plans to archive, a diverged branch.
- **Commits** — the plan, each commit with its message and file list, and which reviewed commit ends at the reviewed
  tree where `layout` named one. Then the push.

For each open item give a short bold title, the quoted words
with their `[N] HH:MM` reference from the digest, one line on why it is still open, and a
recommended disposition.

**A recurring defect is an `answer`, not a `memo`.** A memo parks an idea nobody is doing; it is
the wrong home for something that will present itself again next week, because the next review
rediscovers it and files it a second time. When a finding is a *class* of problem and the project
already has a place that would catch it — `.claude/commit-checks.sh`, a CI workflow, a lint config
— recommend extending **that** place, and name it. Real case: nine dead-code warnings sitting in
every build were offered here as a memo, and the user's answer was to ask why the commit check was
not being taught to fail on them instead; two lines closed the class permanently. This is extending
a gate that already exists to cover a blind spot, which is the opposite of the per-objection guard
`~/.claude/memory/feedback_read_only_review_loop.md` warns against — that one adds a new mechanism
per complaint, this one removes a finding that would otherwise keep coming back.

**Work only another machine can do is a routed ping, not a `memo`.** The backlog is for work
nobody is going to do yet, not for work this machine cannot do: a memo defers it to whoever next
reads it, on whichever box they happen to be on, while the machine that can act has a live session
reachable through the `peer` skill. Offered as a memo and corrected on 2026-09-13 and again on
2026-09-15, so recommend the ping.

**A finding another repo's session has to decide is routed too, even where this machine could act.**
The other-machine test is capability; this one is ownership, and they come apart on a finding this session
could implement but has no standing to settle — whether a convention is worth writing, whether a
shared rule should change. Recommend the ping to the session that owns that repo. Offered as a memo
on 2026-09-18 and corrected: *"discuss with claude agent — either on this machine or air — it's
their work"*. A memo there files the question in the backlog of a repo that cannot answer it.

**A finding in a file the project's upstream owns is reported and nothing else — not a memo, and
not a ping either.** The capability and ownership tests both end at a session that can act; this one ends at an account
nobody here speaks for. A fork's backlog is work this repo has undertaken, and upstream's files are
not it, so a memo parks work nobody here will ever do and a ping has no one to reach. `docs-relevance`
already refuses to patch or memo such a gap in prose, and `screenshot-relevance` in images, and each
reports it instead, which means a finding arriving from either skill carries the reason it stopped —
read it before re-dispositioning, rather than taking the report and choosing afresh. For prose, two
exceptions, both named in `docs-relevance`: the gap touches a change the user
carries on their own branch, or it belongs to an issue they have already raised upstream. Test them
with `git diff --name-only upstream/main...<branch>` rather than from memory. Otherwise the
disposition is `drop`, and an upstream issue only when the user asks for one. On 2026-10-01 a
stale screenshot and a source comment in a third-party fork were both carried in from the
relevance pass's own report and recommended as memos, which is the one disposition it names as forbidden.

**A `--platform` tag does not soften that.** The flag exists for a memo that was going into the
backlog anyway and happens to need one box — not as a way to park work a live session over there
could take now. Route when there is someone to route to; tag when there is not, and the memo was
already the right home.

**Then sequence the send, because routing it is only half the decision.** A ping whose action
depends on this side's work — a commit to pull, a change still uncommitted here — waits for the
push; one the peer can act on immediately goes out with the rest of the dispositions.
Say in the finding which session it goes to and which of the two it is, since that is what the
user is agreeing to.
`~/.claude/memory/peer_messaging.md` owns the rest, including why the wait matters, and the `peer`
skill owns how the message is sent; do not restate either here.

```
**Concerns passed over**

3. **The publish path was never re-tested after the rename**
   [14] 16:02 "I have not re-run publish since renaming the container, so this is unverified."
   Still open: nothing in the session ran it afterwards, and the rename is in the pending diff.
   Recommend: answer now (one command, and the commit depends on it).
```

Every other line carries its recommendation too: save or skip, keep or local, address or not, archive or leave.

Close with the one prompt:

```
Reply `go` to take every recommendation and commit and push, or override by number:
`answer 2`, `memo 3 5`, `ping 4`, `drop 1`, `skip 7`, `hold` (everything but the push).
Anything you do not name keeps its recommendation.
```

Then stop and wait. This is the skill's only gate: nothing is applied, saved, committed or pushed before the answer.

### 8. Apply, commit and push

Apply in this order, without asking again.

**Dispositions.**

- **answer** is ordinary work. Do it now, in full. Its changes were made after the review, so
  they go in follow-up commits after the plan's own; add them to the plan, a group of their own
  unless they plainly belong to one already there. A decision that changes no code is recorded
  by the reflection save below.
- **memo** writes one file per item:
  `python ~/.claude/skills/memo/memos.py add --title "<short title>" "<the detail>"`, adding
  `--platform macos|windows` only when the detail itself names the box the work needs.
  Write each one to stand on its own, naming the thing and the concrete next step. The session
  it came from is about to be cleared, so a memo that only gestures at the conversation
  ("fix the thing we discussed") will be unreadable in three weeks. Title it as a sentence that
  names the thing and the change — it is the only line that shows up in every later listing —
  and put the evidence, the reproduction and the reasoning in the body, which has no length limit.
- **ping** sends the item to the session that owns it, found and reached as the `peer` skill
  describes — `SendMessage` on this machine, `peer_relay.py send --project <project>` for the
  other one. Write the message to stand on its own under that skill's "What goes in the message".
  A ping the peer can act on now goes out here. One that depends on this side's work waits for
  the push below. When no session for that project is live, or
  the send is refused, `NOT SENT` or `unknown`, report it and ask whether to memo the item
  instead — never let a ping that did not go out read as routed.
- **drop** means do nothing at all: no memo, no work, no argument, no raising it again later in
  the same run.
- **A memo number read in step 7 may be stale by now.** The listing is positional and
  newest-first, so a memo the user captures while answering the gate renumbers everything below
  it. Re-run `memos.py list` before any `done <n>`, and key the disposition to the memo's title
  rather than the number you presented. Measured 2026-09-19: a finding presented as memo 4 was
  memo 5 by the time it was closed.

**Saves.** Write what `/reflect` drafted and the answer kept, as its step 7 describes, rendering the memory index
where a global memory changed.

**Decisions.** Apply the rest: apply the clean-up proposals approved, run an approved pending capture (asking right
before it, as the `screenshot` skill says), un-ignore or record untracked skills, archive the finished plans approved,
close the memos the change set delivers (one `memos.py done` call, per `commit-grouping.md`).

**Commits.** Re-run `review_scope.py layout` if anything above changed the tree, regroup only what changed, and
commit each group with `python3 ~/.claude/skills/shared/commit.py -F <message-file> [--reviewed] <paths…>`. A
blocking privacy finding stops here and goes to the user with the finding: it is the one question this step may
ask, since nothing approved at the gate covered content that must not be published. Any other refusal is yours to
fix and retry. Then `python3 ~/.claude/scripts/review_scope.py advance`.

**Push**, unless the answer was `hold`: `python3 ~/.claude/skills/shared/push.py --caller wrap-up`. Report its lines,
then watch CI and hand off files written in other repos as the "After the push" section of `shared/sync-and-push.md`
describes, and send the pings held for the push. If the push failed, send none of the pings and say which are held.

Report in one short block: one line per disposition, the saves, the commits, and the push step's lines, its status
line last.


### 9. Offer to run it here, ship it, and release it

A section of work closed without these leaves the committed change unrun on this machine and its users
on the previous version, and nothing later in the flow mentions it: the push step stops at the
push, and the context that knew a publish was pending is about to be cleared.

**Ship wrappers** says which of the two per-machine wrappers this repo has. A verb reported `absent` is
not configured here, and configuring it is `/deploy`'s and `/publish`'s own job, not this skill's — say
nothing about that verb at all. Where both are absent and the release check below finds nothing, this
step produces no output.

Offer the two separately and in this order, ahead of the release offer, and run each through the repo's wrapper —
`bash scripts/deploy.sh` and `bash scripts/publish.sh`. Not the `/deploy` or `/publish` skill: those own
first-time configuration, and the script is the path for a project already configured
(`~/.claude/memory/feedback_deploy_script_not_skill.md`).

**deploy — run the committed code on this machine.** Offer it when `deploy: present`. Treat every **deploy
type** other than `dev-server` as relaunching an app with a window, so the offer *is* the ask `CLAUDE.md`'s
**Taking Over the Machine** section requires: name the app that gets raised and roughly how long it takes,
and keep the ask immediately before the run. A `dev-server` binds a port and raises nothing, so it needs no
such warning. Exempt that one value rather than listing the window-raising ones: `dev-server` is the only
value `/deploy` ever writes, and every other project type is detected structurally — Tauri from
`src-tauri/tauri.conf.json` — leaving the key absent. So listing the window-raising types would name values
nothing produces, and skip the ask on every project that has one. Report what the run printed, a failure
included.

**publish — ship it outward.** Offer it whenever `publish: present`, with one exception: a push the user
held back with `hold` in step 7. Withhold it there and say why — a project carrying `ALLOW_DIRTY_PUBLISH=1` would ship
that work regardless, and a decision not to put something on the remote is the one thing the script cannot
see, because it reads a configuration.

**pre-publish checks — offered just before the publish offer.** **Ship wrappers** also lists each
`pre-publish:` line a repo declares in its committed `.claude/pre-publish`: a check too slow, too costly or too
nondeterministic for its commit gate, which its owner still wants offered before shipping — an evaluation run
against a live model is the standing case. Offer each one, by its command and the description after its `#`,
right before the publish offer, and run it on a yes, from the repo root. Report what it printed, and a failure
plainly, then make the publish offer anyway: the check informs that decision and does not gate it, since a
nondeterministic one falls short on some runs by its nature. A repo with no such file lists none, and then
say nothing about it.

**Do not restate the script's own shipping guard here.** It decides what is shippable, and a second copy of
that rule in this file drifts from it: writing "the script refuses an unpushed tree" without the
`ALLOW_DIRTY_PUBLISH=1` waiver makes this step contradict the `publish` skill's own page, and withholds the
offer for good on the projects that carry the waiver. Offer, and report the refusal as the outcome where one
comes back.

**release — cut a version.** Run `bash ~/.claude/skills/wrap-up/scripts/release_candidates.sh` after the
publish offer is settled; it has to run here rather than in Context, because Context was read before this
section's commits existed. Offer `/release` when it reports one or more feat/fix commits since the last `v*` tag,
and list those subjects in the offer so the user judges them — `/release` decides the version and whether a
change reaches the shipped artifact, so do not pre-judge either here. Say nothing when it reports zero, no tag, or
not a git repo: a project that has never been tagged takes its first release deliberately, not from a wrap-up.
A `FETCH-FAILED` line means a release cut on the other machine may be missing from the count; say so in the
offer. Withhold it after a `hold`, as with publish: a release tags and pushes on top of
the work they kept off the remote. Invoke it through the Skill tool, since no wrapper exists for it, and
treat its own gates as the authority on whether it can proceed. A "yes" to deploy or publish does not carry to it.

A clean tree with nothing to commit leaves step 8 no commits to make, and its push sends only commits made earlier and
not yet pushed — an earlier `hold`, `/adopt` or `/review-manual` leaves some — if there are any. That still
gets the offers: the work may have been pushed earlier in the session, and this step is the last thing that
will mention it before the context is cleared. What the offer cannot know is whether the target is already
serving that commit, so it may propose a publish that changes nothing — reading the deployed revision is
the script's business, not a precondition to guess at here.

The `publish` skill's **Authorization** section binds this offer as much as a typed `/publish`: the user has
to name publishing, so a "yes" carried over from the deploy offer does not clear it — ask for the verb. That
script proves success by observing the live target rather than by building cleanly; report what it
observed, and never call a publish done on a green build.

**Do not fold any of these offers into step 7's gate.** All of them are asked after the push: the
machine-takeover ask is valid only immediately before the thing it drives, and a publish or release agreed to
at the gate is agreed to before the user has decided whether to push the work it would ship.

### 10. Hand over to `/clear`

Once the push is confirmed, close with a single line telling the user to run `/clear`, and say
what it buys: the next transcript begins at that point, which is what keeps a future `/wrap-up`
scoped to exactly one section of work.

This skill cannot run it. Clearing the context is a built-in CLI command, not a skill or a
tool, so the user has to type it. Recommend it, do not claim to have done it, and do not
recommend it at all after a `hold` or a failed push, since clearing on top of unpushed
work throws away the context needed to finish it. A run in step 9 that failed and left something
to fix withholds it for the same reason: the session holding the output is the one that can act
on it.

## Out of scope

- Do NOT act on an item the user marked memo or drop.
- Do NOT re-raise anything an earlier `/wrap-up` in this session already settled.
- Do NOT read another session's transcript, or files under `~/.claude/projects/` by hand; the
  digest is the only session source this skill uses.
- Do NOT do `/reflect`'s job. It captures durable knowledge; this skill captures unfinished
  business. Both run, and they do not overlap.
- Do NOT invoke another top-level skill to commit or push, and do NOT run `git add`, `git commit`
  or `git push` directly; `commit.py` and `push.py` carry the checks.
- Do NOT configure a deploy or a publish path here, or raise a missing wrapper as a finding. Step 9
  offers what the repo already has; `/deploy` and `/publish` own the configuration, and a project
  that publishes from CI is supposed to have no publish wrapper at all.
- Do NOT offer a publish or a release after a `hold`, and do NOT treat the
  gate in step 7 as consent for any of the runs in step 9.
- Do NOT predict in step 9 what `deploy`, `publish` or `/release` will refuse. Offer, run, and report what the
  script said; its preconditions are its own to enforce. Reading **deploy type** to decide whether
  the machine-takeover ask needs a window warning is not that — it is this skill's own obligation,
  and it fails to the asking side.
- Do NOT claim to have cleared the context.

## Important

- The gate in step 7 is the skill, and it is the only one. Committing before the user has
  answered defeats the reason for looking at all; asking again after it defeats the reason
  for asking once.
- Present a finding only after checking it is still live. An item the user has to dismiss
  because a file already answers it costs more trust than the item was worth.
- Quote the user and yourself accurately from the digest, with the reference so either can be
  located. Do not paraphrase a concern into something sharper than what was actually said.
- The `allowed-tools` list above deliberately covers only this skill's own machinery, sending a
  ping included. Answering
  a finding in step 8 is arbitrary work and goes through the normal permission flow; do not
  narrow the step to fit the list.
