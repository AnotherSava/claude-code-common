---
name: upstream-sync
description: >-
  Catch a fork up with the third-party project it tracks, then triage what upstream shipped — find where
  incoming commits touch the fork's own patches and what each fork commit should become, integrate on the
  user's go-ahead, and walk the new features against how the user actually uses the product, on a page the
  discussion is recorded in.
  TRIGGER when: the user asks to pull, merge or rebase upstream changes into a fork and analyze them; asks
  which upstream changes affect their fork's patches; or asks what new upstream features are useful to them.
  DO NOT TRIGGER when: the branch only lags its own remote (that is `/pull`), the repo is not a fork of
  someone else's project, or the task is filing an issue or PR upstream.
---

# Upstream sync

A fork carries the user's patches on top of somebody else's project. Each upstream catch-up asks three
questions, in this order: what in the incoming range collides with the fork's patches, what the fork should
look like after it, and which of upstream's new features matter to the user's own work. The first two decide
the integration; the third is a discussion that outlives this session, so it lives on a page.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints, and
`~/.claude/learnings/git-resolving-rebase-conflicts.md` before resolving anything.

## Context
- Remotes: !`git remote -v`
- Branches: !`git branch -vv`
- Status: !`git status --short; echo "(end of status)"`

## 1. Establish the topology

**Context** is gathered before the fetch below, so its ahead/behind counts are stale; measure after fetching.

Read the project memory first (`.claude/memory/`): a fork note usually records which remote is the
user's, which is the third party's, which branch carries the patches, and how the app is installed.
Confirm it against **Remotes** and **Branches** rather than trusting it. Name, for the rest of the run:

- **upstream ref** — the third party's remote-tracking ref, e.g. `upstream/main`. It may be the patch branch's
  own `@{upstream}` (remotes inverted). Never a local mirror branch such as `main`, which can lag it.
- **patch branch** — the branch holding the fork's commits, and the remote it is pushed to.
- **integration method** — rebase or merge. Read it from the fork's own history:
  `git log --merges --oneline <upstream ref>..<patch branch>` empty means rebase. Unscoped, the log lists
  upstream's own PR merges and reads as "merge". Do not switch methods unasked.

Fetch with `git fetch --all || echo FETCH-FAILED`. A failed fetch makes every count below unmeasured; stop
and say so.

Trust git for "is there anything new", never the app's own update check: a fork's version string can blind it.

## 2. Measure the range

1. Behind/ahead: `git rev-list --left-right --count <upstream ref>...<patch branch>`.
2. Fork-only commits: `git log --oneline <upstream ref>..<patch branch>`.
3. Version range: the merge base's nearest tag to the upstream ref's tag (`git describe --tags`), and the
   upstream `CHANGELOG.md` sections in that range (`git show <upstream ref>:CHANGELOG.md`). Without tags or
   a changelog, read every subject in `git log <merge-base>..<upstream ref>`, not only `feat:`/`fix:` ones:
   a non-conventional subject can be the biggest feature. For a `(#N)` subject, `gh pr view N --repo <upstream>`.

## 3. Find what collides with the fork

With `B=$(git merge-base <patch branch> <upstream ref>)`, intersect the files each side changed:
`comm -12 <(git diff --name-only $B <patch branch> | sort) <(git diff --name-only $B <upstream ref> | sort)`.
Then predict the textual conflicts without touching the tree: `git merge-tree --write-tree --name-only <upstream ref> <patch branch>`.
That predicts a merge. A rebase replays each commit, so a file touched by N fork commits can conflict N times
where merge-tree reports once. For the exact picture on a rebase fork, rebase in a scratch worktree under
the gitignored `tmp/` and remove it afterwards.

Find fork commits upstream already took (the user's own PR, merged): `git cherry -v <upstream ref> <patch branch>`;
a `-` line is patch-identical upstream.

For every fork commit, read its diff beside upstream's diff of the same files and classify it:

| Class | Sign | What the fork commit becomes |
|---|---|---|
| Independent | no shared files | rebases as is |
| Upstream merged it | `-` in `git cherry` | the rebase drops it; update any memory recording the PR as open |
| Upstream built the same mechanism | same apply loop, stamp, config key, under upstream's names | shrink the fork commit to what upstream lacks; take upstream's version of the rest |
| Upstream fixed the reason | the fork patch's symptom is gone upstream | propose dropping it; verify the symptom before saying so |
| Ordered resources | both sides add numbered patches/migrations | renumber the fork's after upstream's, and amend any doc that says "the final patch" |
| **Semantic interaction** | no shared lines, but upstream added code or tests in the area the fork patch changes behaviour of | flag it; this is the one that passes the rebase and fails CI |

The last row needs a deliberate search over the lines upstream added, for the symbols the fork patch touches:
`git diff $B <upstream ref> -- <src dirs> <test dirs> | grep '^+' | grep -E '<symbols>'`. Real case: a fork libghostty patch treating clicks-only
mouse mode as uncaptured rebased cleanly, then failed two upstream tests added in the same range, because
the app still asked an unpatched "is the mouse captured" query and the two halves disagreed.

When the fork carries patches against a vendored dependency, prove they stack: a scratch checkout of the
pinned revision under the repo's gitignored `tmp/`, apply upstream's patches, then `git apply --check` the
fork's. Delete the scratch checkout afterwards.

Check whether the fork's patches still serve a purpose upstream's new features rely on: upstream docs
saying a workaround is still needed is evidence the patch stays.

## 4. Inventory how the user uses the product

The feature triage is only as good as this. Gather, read-only:

- **Transcripts:** count CLI subcommands across every project, on the machine that runs the product
  (over SSH when that is the other one; otherwise report the count unmeasured), e.g.
  `grep -ohE "<tool>ctl(\.exe)? [a-z-]+( [a-z-]+)?" ~/.claude/projects/*/*.jsonl | sort | uniq -c | sort -rn | head -25`.
- **Integrating repos:** delegate one `Explore` agent to list every call the user's other repos make into
  the product (dashboards, skills, scripts), with file, function and what each call is used for. A call
  existing is not relevance: a `session new` that only runs an attach script never cares which cwd it
  opens in. When the product is a terminal or app with a live control socket, its prompt carries the
  project's own safety line verbatim (agterm's:
  "never execute `agterm`/`agtermctl` against the default socket, never launch or quit the app, static
  reading only."); for a product with none written down, adapt that one.
- **Memories and memos** of the integrating repos that name a missing capability: an upstream feature may
  answer an ask recorded as withdrawn or impossible.

Read the installed version with the product's own version command (e.g. `<tool>ctl version`) on the machine
that runs it: a feature is unusable until the user redeploys there.

## 5. Report, then stop

One reply, two sections:

1. **Incoming changes that overlap your fork** — per fork commit, its class from step 3 and the concrete
   rework, numbered. Say what was verified (apply-check, merge-tree) and what was inferred.
2. **New features useful for your work** — the top few with one line each tying them to an inventory
   finding; say the full list comes on a page after integration.

End by asking to integrate. A diverged branch is never rebased or merged without that answer.
The session that ran steps 1-5 asks it, and names where step 6 will run.

## 6. Integrate

Steps 1-5 may run on either machine; step 6 runs where the patch branch is owned. When that is another
session, hand it off through the `peer` skill with the step 3 plan and the user's answer. The receiver
re-measures (rev-list, `git cherry`, merge-tree) before rebasing, since the range may have moved.

1. Rebase or merge by the method from step 1. Resolve per the step 3 plan; mid-rebase `--ours` is the
   upstream side (the learnings file has the detail).
2. Update the fork's own record of its patches in the same change: the patches README, the fork memory note,
   and any fork version bump. Commit these through `shared/commit.py`, so the branch carries its own
   description whenever it is pushed.
3. Rebuild whatever the dependency stamps say is stale, then run the project's real gate (its
   `commit-checks.sh` or the build plus tests its CLAUDE.md names). The patch branch is pushed only once it
   is green. When the gate only runs on a machine other than the one holding the patch branch, it goes to
   the live session there (the `peer` skill), not skipped. That session can only build what is pushed, so
   push the rebased branch to a scratch branch on the fork for it, and delete the scratch branch once it
   reports.
4. A semantic interaction from step 3 that the gate confirms is fixed in the fork's patch, not by editing
   upstream's code. Upstream tests asserting upstream's behaviour get a one-line skip naming the fork patch,
   so each future sync conflicts on one line. Ask before skipping.
5. Ask when to push: now, or after the feature discussion. The integration is already committed (item 2), so
   this decides only when the push runs. A merged branch pushes plainly through `shared/push.py`. A rebased
   one goes out as "Pushing a rebased fork needs a force push" says, never through `/wrap-up` or
   `push.py`: `/wrap-up`'s sync reads the rebased branch as diverged.

**Pushing a rebased fork needs a force push.** `shared/push.py` runs a plain push, which is refused. Propose
`git push --force-with-lease=<branch>:<remote>/<branch> <remote> <branch>` and run it only on a yes, then do
by hand what `push.py` does after a push, as `shared/sync-and-push.md`'s "After the push" lists. Query CI with an
explicit `--repo <fork owner>/<name>`: in a fork `gh` resolves to upstream by default. A macOS job cancelled
after ~15 minutes without a step is runner shortage, so the run measured nothing; say so instead of
calling it green or red.

Never tag or release from the fork: version tags are upstream's.

## 7. The features page

Write `tmp/<project>-v<from>-v<to>-features.html` (gitignored scratch), following system light/dark:

- One numbered card per new feature, grouped by theme, bug fixes left out. Keep numbers stable for the
  whole discussion: the user refers to items by number.
- Under each card, an assessment against the step 4 inventory, tagged `improves existing`,
  `new capability` or `low relevance`, with the reason. Highlight the strongest.
- Add, as item 0, anything older than the range that the inventory shows the user believes is missing.
- A **Discussion context** section at the bottom: fork state (running version, what the fork patches now
  change, CI status and the retry command, what was sent to other sessions), the integration inventory, and
  points already discussed. It is what lets the discussion survive `/clear`.

Publish it with `python3 ~/.claude/skills/shared/tailnet_publish.py publish <file>` and hand over the URL it
prints. Inside agterm, also offer to open it in an overlay (the `agterm` skill).

## 8. The discussion

Go one item at a time, at the user's pace. For each decided item:

1. Move it from a **Pending** table to a **Processed** one at the bottom, with a one-line decision.
2. Carry out the decision's routing: a memo in this repo (`/memo`), a message to the live session owning
   another repo (`peer` skill; no approval needed), or nothing. A memo for another repo goes through that
   repo's session, never written into its tree from here.
3. Update the page and say what changed in it.

When the user wants to break off, update the Discussion context and give them, in a fenced block, the line
that resumes it:

```
read tmp/<page>.html, including the discussion context at the bottom, and let's continue discussing it
```

The page is temporary: it ends when nothing pending is left that the user values. Do not propose keeping
it as a long-term document.

## Out of scope

- Filing issues or PRs upstream: outward communication, drafted and approved per message.
- Deploying or restarting the installed app: offer it, with the project's own deploy rules.
- Tagging or releasing.
- A fork that is only behind its own remote: `/pull`.
