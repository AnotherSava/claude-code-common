---
name: adopt
description: >-
  Bring one repo up to date with the conventions defined in the claude dotfiles repo — walk the
  convention versions this repo has not adopted yet, perform each migration, confirm the continuing
  rules hold, and hand the new number to /commit.
  TRIGGER when: the user runs /adopt; a session-start message says this repo is N versions behind or
  has no convention record; or the user asks where this repo stands on the conventions.
  DO NOT TRIGGER when: the task is authoring a NEW convention version — that is work in the dotfiles
  repo, and `claude/conventions/authoring.md` is its contract — or the repo is a third-party clone,
  which adopts nothing and records nothing.
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Skill, Bash(echo *), Bash(git rev-parse:*), Bash(git fetch:*), Bash(git log:*), Bash(git status:*), Bash(git check-ignore:*), Bash(git show:*), Bash(git ls-files:*), Bash(git diff:*), Bash(git -C ~/.claude/skills:*), Bash(python ~/.claude/conventions/engine.py:*), Bash(python ~/.claude/conventions/check.py:*), Bash(python ~/.claude/conventions/versions/:*), Bash(python ~/.claude/hooks/check-install.py:*)
---

# Adopt

A convention defined in the dotfiles repo is a claim about every repo on this machine, and changing one
leaves the rest in the old shape. Every change an already-conforming repo has to *do something* about
ships as a numbered **version**: a folder of prose saying what changed, how to migrate an existing repo,
when the migration is a no-op, and which continuing rule — if any — the version hands to the checker.
This skill walks the versions this repo has not adopted, one at a time, and moves its number up by one
for each.

A version is a migration, so the walk performs it. Most versions carry prose rather than a script, and
reading that prose and doing what it says *is* the adoption. Where a migration deletes or rewrites a
committed file, the README says what would be lost — show that and get a yes before running it.

The session-start notice that sends the user here is a `systemMessage` — it reaches their screen and
never the transcript — so the gap is re-derived below rather than taken from what they pasted.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || echo "(not a git repo)"`
- This repo, commits it is behind its upstream: !`git fetch -q 2>/dev/null || echo "(fetch failed — what follows compares against the last fetch that worked)"; git log --oneline HEAD..@{upstream} 2>/dev/null || echo "(no upstream configured)"; echo "(end of list)"`
- Dotfiles checkout, commits it is behind its upstream: !`git -C ~/.claude/skills fetch -q 2>/dev/null || echo "(fetch failed — what follows compares against the last fetch that worked)"; git -C ~/.claude/skills log --oneline HEAD..@{upstream} 2>/dev/null || echo "(no upstream configured)"; echo "(end of list)"`
- Record file ignored by: !`git check-ignore -q "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/conventions" && git check-ignore -v "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/conventions" || echo "(not ignored — the record will be tracked, unless Repo root above says this is not a repo at all)"`
- Install check: !`python ~/.claude/hooks/check-install.py 2>&1 | grep FAIL || echo "(every symlink and git setting resolves)"`
- Conventions status: !`python ~/.claude/conventions/engine.py status "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" 2>&1`

The dotfiles line reaches the checkout through `~/.claude/skills` because that link is live by
construction — this file was loaded through it — and `~/.claude/conventions` is the same working tree
seen through a second link.

Two of those lines have a trap in them, and both are why they are written the way they are. A
commit line appearing above `(end of list)` is the only thing that means behind — an empty `git
log` and a `fetch` that failed print the same nothing otherwise, so offline would read as up to
date. And the ignore line asks `check-ignore -q` for the yes-or-no, using `-v` only to explain it:
the `-v` form exits **0 on a negated pattern**, printing `!.claude/conventions` as the matching
rule for a file it is reporting as *not* ignored, so a record correctly re-included by the fix
below would otherwise read as still hidden and every later run would loop on a `.gitignore` that is
already right.

## What the number means

The record is `<repo>/.claude/conventions` — committed, one integer on its own content line. `vN` says
every migration up to and including N was performed here, in ascending order, by a session that read it.
Three things it deliberately does not say:

- **That the repo still conforms.** A property that has to hold *continuously* is a rule, re-measured by
  `~/.claude/conventions/check.py` — which the repo's commit gate runs, and which this walk runs too. The
  number is history; the checker is the present tense.
- **That every version applied.** A version whose `## When it does not apply` is satisfied here ran to a
  no-op, and the number advances just the same. There is no `n/a` and no `declined`: an exception to a
  convention belongs *in* the convention, written into that section and re-evaluated in every repo, not
  remembered per repo as a line nobody re-reads.
- **That a machine-scoped version is wired on this machine.** That is the gitignored
  `.claude/conventions.local`, which does not travel, so a fresh clone reports the symlink it has not
  made rather than inheriting the other machine's answer.

A repo that must never adopt carries `exempt <reason>` on that content line instead of a number.

What can never carry a version at all — agent behaviour, code content, an unbounded property, a global
setting — is enumerated in `~/.claude/conventions/not-versioned.md`. Read it when the user asks what
"current" covers, so the answer is "every versionable convention has been adopted" rather than
"everything in CLAUDE.md is satisfied here".

## 0. Gates, before anything is read or run

- **Not a git repo** — if **Repo root** says so, stop. A record written here would be a file nothing
  tracks, in a directory no clone ever sees, and the engine would report it as written. Three real
  project directories on this machine have no `.git` at all, which is why the session-start notice says
  so rather than staying silent — and that notice is the most likely reason someone typed `/adopt` here.
  Offer `git init` as its own decision, not as part of this walk.
- **This repo behind its upstream** — if **This repo, commits it is behind its upstream** shows any
  commit line above `(end of list)`, propose the sync and stop. A migration that deletes a file the other
  machine just appended to merges cleanly and loses the append silently; that near-loss is written up in
  `~/.claude/learnings/git-stash-pull-safety.md`, and the tree is dirty by premise here, so follow that
  file rather than reaching for `git pull --rebase`.
- **The dotfiles checkout behind its upstream** — if **Dotfiles checkout, commits it is behind its
  upstream** shows any commit line above `(end of list)`, stop and propose pulling it. A walk run from a
  stale checkout records this repo as current against a `latest` that has already moved.
- **The record must be trackable** — if **Record file ignored by** names a file, line and pattern, the
  record would be untracked and therefore worthless. Fix the repo's `.gitignore` first: a wholesale
  `.claude/` exclusion becomes `.claude/*` plus explicit `!` re-includes, because git cannot re-include
  a path underneath an excluded directory. Show the edit and apply it on a yes.
- **A dirty working tree is not a gate.** Do not refuse on uncommitted changes and do not ask the user
  to stash them. Several repos hold a convention's work already done and never committed; the new number
  and that pending change commit together at §4, which is what makes them the best-verified case rather
  than a refusal.
- **Install check** is report-only and never blocks. Mention any `FAIL` line it produced: a
  `~/.claude/hooks` that is a copy rather than a link freezes the session-start notice forever, so this
  repo would go quiet about being behind without anything appearing to break.

## 1. Read the gap

Take the pending versions from **Conventions status** in Context — number, slug, scope, title, and the
rules each introduces.

- An `exempt` line stops the run here. Report the reason it records and which of the two files it came
  from — the local one is gitignored, so an exemption there silences this repo on one machine only and
  travels nowhere.
- Nothing pending: say the repo is current and name the version it is current *through*. Then run
  `python ~/.claude/conventions/check.py "<repo root>"` anyway and report what it says, because current
  is a statement about migrations and the checker is the one that can still find something broken.
- **A record naming a version above this checkout's newest one** — status prints this as its own line —
  means the dotfiles repo here is behind the machine that wrote the record. Stop and propose pulling it.
  This is a different condition from §0's dotfiles gate, which compares the checkout with its own
  upstream and stays clean whenever the other machine pushed the repo but not the dotfiles.
- **A machine-scoped version adopted here but not wired on this machine** prints as its own line too. Do
  the machine-side work its README describes and report it — then raise it with the user rather than
  hand-editing `.claude/conventions.local`, because the engine advances that file only alongside the
  committed number, and a hand-written local number would claim every machine-scoped version below it
  was wired here as well.

## 2. Walk the pending versions, one at a time, ascending

One version per pass, in number order. Never batch them, never reorder them, and never start the next
before the current one's number is recorded — a later migration may depend on what an earlier one wrote.
The engine enforces the order anyway: `adopt` takes only the current number plus one.

1. **Read the version's README in full first** — `~/.claude/conventions/versions/<NNN-slug>/README.md`,
   every heading, before touching anything. Its four sections are what the rest of this pass runs on:
   what changed and why, how to migrate an existing repo, when the migration is a no-op here, and the
   continuing rule the version hands to the checker.

2. **Settle `## When it does not apply`, with the positive evidence it asks for.** Name the command you
   ran or the file you read and show what came back; "nothing found" and "nothing looked at" must not
   read the same (`~/.claude/memory/feedback_not_run_is_not_pass.md`). If none of its conditions holds,
   the migration applies here — continue. If one does, change nothing and go to sub-step 5.

3. **Check whether the repo is already in the target shape.** Work done by hand, or on the other machine
   days ago, is common, and the answer is the same as a no-op: change nothing and go to sub-step 5. Say
   which of the two it was, since "already in this shape" and "does not apply here" are different facts
   that leave the same empty diff.

4. **Do the migration.**
   - **Where the README carries a question, put it to the user verbatim** — unedited, unsummarised,
     nothing added but the repo's name if that is not already obvious. A question exists precisely
     because no file can settle it, so a plausible answer read off the surrounding repo is the guess
     `~/.claude/memory/feedback_surface_the_gap_dont_fill_it.md` forbids. If their answer amounts to
     "not here", treat it as sub-step 2's no-op and say so — their reason is stored nowhere, so if it
     would hold for every repo it belongs in that version's `## When it does not apply` or in a later
     version, which is work in the dotfiles repo and its own session's task. Offer a memo for it.
     If their answer is that it applies and they do not want it done, that is a §3 stop.
   - **Where the folder carries an `apply.py`, run it** rather than doing the work by hand —
     `python ~/.claude/conventions/versions/<NNN-slug>/apply.py "<repo root>"`. It exists because the
     work is mechanical and tedious, it prints what it did, and it exits non-zero on any line it cannot
     classify, which is a §3 stop with the tree left as it found it.
   - **Otherwise perform it yourself**, following the README's named files and transformation. Where it
     deletes or rewrites a committed file, show what would be lost and how to compare against the diff,
     and get a yes before doing it. Ordinary additions need no ceremony — do them and show the result.
   - Then run the README's own after-the-migration check and report what it returned.

5. **Advance the number by one:** `python ~/.claude/conventions/engine.py adopt "<repo root>" <N>`.
   It refuses to lower the number, to skip one, or to go above the newest version in this checkout, and
   a refusal is a §3 stop rather than something to work around.

6. **Run the checker:** `python ~/.claude/conventions/check.py "<repo root>"`. Exit 0 is done; exit 1 —
   a violation or a rule that could not be measured — is a §3 stop. It runs *after* the number moves
   because it runs the rules introduced at or below the adopted version, so the rule this version brings
   in is unmeasurable until the record names it. That order is safe in the direction that matters: the
   number only ever claims the migration ran, and this repo's commit gate re-runs the same checker, so a
   half-done migration cannot reach a commit. Report which rules ran — a version whose
   `## Continuing rule` says `None` adds nothing to that list, and the list is how you can tell.

## 3. The first failure stops the run

A migration you cannot complete, an `apply.py` exiting non-zero, an `adopt` refusal, a `check.py` exit 1,
or a user who wants the convention's work not done — any of these ends the walk. Leave the tree exactly
as it is, name the failing items whatever printed them reported, and say which versions were adopted
before it. Do not skip the failing version and carry on with the next: later migrations may depend on it,
and the engine will refuse the skip regardless. The repo stays behind at that number, and the
session-start notice keeps saying so, which is the pressure working rather than a gap being filed away.

## 4. Hand to /commit

Run `/commit`. One commit for the whole walk, subject:

```
chore(conventions): adopt through vN
```

N is the new number — re-run `engine.py status` to read it rather than counting the versions you walked.
The record and whatever the migrations changed in the working tree commit together; `/commit` is what
runs `.claude/commit-checks.sh`, the confidentiality scan and the memo and issue notices, so nothing here
commits directly.

Two things to say once the walk is over. If this repo's `.claude/commit-checks.sh` does not run
`check.py`, the rules this walk just took on were measured by the walk and by nothing since — say so
rather than leaving "adopted" to read as "checked from here on". And if the record file conflicts on a
later pull, both machines walked from the same base: keep the higher number, whose migrations are all
present in the merged tree.

## There is no audit step

Re-checking is only meaningful for a property that has to keep holding, and such a property must not be
sampled by a command someone has to remember to run. That half is the commit gate's: `check.py` measures
every rule the repo's number entitles it to, on every commit, and reports a rule it could not measure as
unmeasured rather than as a pass. Nothing re-derives a migration afterwards, because a migration is not a
standing claim — it ran, and the number says how far.

## Out of scope

- **Never touch another repository.** The session running in a repo is the only one that may commit
  there. A repo found behind is reported, never adopted from here.
- Do not author a new convention version. That happens in the dotfiles repo, in the session that is
  changing the convention itself, not in the one adopting it here.
- Do not edit a shipped version's README or its `apply.py` to make this repo pass. A version folder is
  shared by repos that run it at different times, so editing one gives two repos different behaviour
  under one number; a convention that is wrong is corrected by a later version. A fix to how a *rule*
  detects something is different — that belongs in `rules/`, where it applies everywhere at once.
- Do not hand-write, or lower, either record file. The engine's `adopt` is the only writer, and one
  version at a time is what keeps the number from claiming a migration nobody read.
- Do not create the artifact a version's `## When it does not apply` says is absent — an empty
  `.claude/memos/`, a guessed `LICENSE`, an invented `engines.node`. The no-op is the version working
  correctly.
