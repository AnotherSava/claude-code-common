---
name: adopt
description: >-
  Bring one repo up to date with the conventions defined in the claude dotfiles repo — walk every
  convention version this repo has not decided yet, apply what applies, record why the rest was
  skipped, and hand the record to /commit.
  TRIGGER when: the user runs /adopt; a session-start message says this repo is N versions behind or
  has no convention record; or the user asks where this repo stands on the conventions.
  DO NOT TRIGGER when: the task is authoring a NEW convention step (read
  `~/.claude/skills/adopt/references/authoring-a-step.md` instead), or the repo is a third-party
  clone — those are exempt and record nothing.
allowed-tools: Read, Edit, AskUserQuestion, Skill, Bash(echo *), Bash(git rev-parse:*), Bash(git fetch:*), Bash(git log:*), Bash(git status:*), Bash(git check-ignore:*), Bash(git show:*), Bash(git -C ~/.claude/skills:*), Bash(python ~/.claude/skills/adopt/conventions.py:*), Bash(python ~/.claude/skills/adopt/steps/:*), Bash(python ~/.claude/hooks/check-install.py:*)
---

# Adopt

A convention defined in the dotfiles repo is a claim about every repo on this machine, and changing one
leaves the rest in the old shape. Every change an already-conforming repo has to *do something* about
ships as a numbered **step**: prose saying why it changed and what it does not apply to, plus a script
that probes, applies and verifies. This skill walks the steps this repo has not decided yet, one at a
time, and leaves a committed record of every decision.

Nothing runs unattended. Each mutation is shown as a dry run and applied only on a yes, and every
question a step cannot settle by itself goes to the user in the step's own words.

The session-start notice that sends the user here is a `systemMessage` — it reaches their screen and
never the transcript — so the gap is re-derived below rather than taken from what they pasted.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || echo "(not a git repo)"`
- This repo, commits it is behind its upstream: !`git fetch -q 2>/dev/null || echo "(fetch failed — what follows compares against the last fetch that worked)"; git log --oneline HEAD..@{upstream} 2>/dev/null || echo "(no upstream configured)"; echo "(end of list)"`
- Dotfiles checkout, commits it is behind its upstream: !`git -C ~/.claude/skills fetch -q 2>/dev/null || echo "(fetch failed — what follows compares against the last fetch that worked)"; git -C ~/.claude/skills log --oneline HEAD..@{upstream} 2>/dev/null || echo "(no upstream configured)"; echo "(end of list)"`
- Record file ignored by: !`git check-ignore -q "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/conventions.tsv" && git check-ignore -v "$(git rev-parse --show-toplevel 2>/dev/null)/.claude/conventions.tsv" || echo "(not ignored — the record will be tracked, unless Repo root above says this is not a repo at all)"`
- Install check: !`python ~/.claude/hooks/check-install.py 2>&1 | grep FAIL || echo "(every symlink and git setting resolves)"`
- Conventions status: !`python ~/.claude/skills/adopt/conventions.py status "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" 2>&1`

Two of those lines have a trap in them, and both are why they are written the way they are. A
commit line appearing above `(end of list)` is the only thing that means behind — an empty `git
log` and a `fetch` that failed print the same nothing otherwise, so offline would read as up to
date. And the ignore line asks `check-ignore -q` for the yes-or-no, using `-v` only to explain it:
the `-v` form exits **0 on a negated pattern**, printing `!.claude/conventions.tsv` as the matching
rule for a file it is reporting as *not* ignored, so a record correctly re-included by the fix
below would otherwise read as still hidden and every later run would loop on a `.gitignore` that is
already right.

## What a recorded line means

The record is `<repo>/.claude/conventions.tsv` — committed, tab-separated, one line per decision, sorted
by version. Four states and nothing else:

| State | Who decided it | What it claims |
|---|---|---|
| `applied` | the step's own `verify`, in the run that wrote the line | this repo was in the target shape at that moment |
| `n/a` | a `probe` exit 1, or the user answering a `probe` exit 2 | the convention does not apply here, for the recorded reason |
| `declined` | the user | it applies and they chose not to |
| absence | nobody | not run — a missing line can never read as a pass |

A repo that must never adopt carries one bare line instead — `exempt<TAB><reason>`.

A step whose frontmatter says `scope: machine` splits across the two files, and `conventions.py record`
does the splitting. An `applied` line is written **twice**: into the committed record, which travels and
says the repo decided this, and into the gitignored `.claude/conventions.local.tsv`, which does not and
says this machine wired it. A fresh clone then has the first and not the second, so it reports the step
as decided here but not wired on this machine instead of silently inheriting the other machine's
symlink. An `n/a` or a `declined` is written only to the committed record — "there is no
`.claude/memory/` to point at" is a fact about the repo, true on every machine, and burying it in the
gitignored file would make each machine answer it again.
The `adopted-through` number is derived, never stored: the highest version such that every step at or
below it has a line in one of the two files.

What can never be a step at all — agent behaviour, code content, an unbounded property, a global
setting — is enumerated in `references/not-versioned.md`. Read it when the user asks what "current"
covers, so the answer is "every versionable convention has been decided" rather than "everything in
CLAUDE.md is satisfied here".

## 0. Gates, before anything is read or run

- **Not a git repo** — if **Repo root** says so, stop. A record written here would be a file nothing
  tracks, in a directory no clone ever sees, and `conventions.py` would report it as written. Three
  real project directories on this machine have no `.git` at all, which is why the session-start
  notice says so rather than staying silent — and that notice is the most likely reason someone
  typed `/adopt` here. Offer `git init` as its own decision, not as part of this walk.
- **This repo behind its upstream** — if **This repo, commits it is behind its upstream** shows any
  commit line above `(end of list)`, propose the sync and stop. A step that deletes a file the other machine just appended to
  merges cleanly and loses the append silently; that near-loss is written up in
  `~/.claude/learnings/git-stash-pull-safety.md`, and the tree is dirty by premise here, so follow that
  file rather than reaching for `git pull --rebase`.
- **The dotfiles checkout behind its upstream** — if **Dotfiles checkout, commits it is behind its
  upstream** shows any commit line above `(end of list)`, stop and propose pulling it. Steps run from a stale checkout would
  record this repo as current against a `latest` that has already moved.
- **The record must be trackable** — if **Record file ignored by** names a file, line and pattern, the
  record would be untracked and therefore worthless. Fix the repo's `.gitignore` first: a wholesale
  `.claude/` exclusion becomes `.claude/*` plus explicit `!` re-includes, because git cannot re-include
  a path underneath an excluded directory. Show the edit and apply it on a yes.
- **A dirty working tree is not a gate.** Do not refuse on uncommitted changes and do not ask the user
  to stash them. Several repos hold a convention's work already done and never committed; the record
  line and that pending change commit together at §5, which is what makes them the best-verified case
  rather than a refusal.
- **Install check** is report-only and never blocks. Mention any `FAIL` line it produced: a
  `~/.claude/hooks` that is a copy rather than a link freezes the session-start notice forever, so this
  repo would go quiet about being behind without anything appearing to break.

## 1. Read the gap

Take the pending steps from **Conventions status** in Context — version, slug, title, scope, and whether
the step carries a script.

- An `exempt` line stops the run here. Report the reason it records, and which of the two files it
  came from — the local one is gitignored, so an exemption there silences this repo on one machine
  only and travels nowhere.
- Nothing pending: say the repo is current, name the version it is current *through*, and stop.
- **A record naming a version above this checkout's newest step** — status prints this as its own
  line — means the dotfiles repo here is behind the machine that wrote the record. Stop and propose
  pulling it. This is a different condition from §0's dotfiles gate, which compares the checkout with
  its own upstream and stays clean whenever the other machine pushed the repo but not the dotfiles.
- A step marked `(retracted at vN — record n/a)` is not walked: the user reversed that convention, so
  record `n/a` with the note `retracted at vN` and move to the next step. Do not read its prose to the
  user, do not run its script, and do not ask its question — a retracted judgement step would
  otherwise put a question to every repo that never got to it. A repo that already holds an `applied`
  line for it keeps that line; the retracting step is what performs the undo.

## 2. Walk the pending steps, one at a time, ascending

One step per pass, in version order. Never batch them, never reorder them, and never start the next one
before the current one has a recorded line — a later step may depend on what an earlier one wrote.

1. **Read the step's prose in full first** — `~/.claude/skills/adopt/steps/<slug>.md`, every heading,
   before running anything. It carries what the convention is for, what it deliberately does not apply
   to, the by-hand checks the script cannot make, and — where it rewrites or deletes a committed file —
   a `## Fetch before running` heading. A step with **no `.py` beside it** is judgement only: skip
   straight to sub-step 4 and put the question under its `## Cannot tell` heading to the user.

2. **Run `verify` FIRST, before `probe`:**
   `python ~/.claude/skills/adopt/steps/<slug>.py verify "<repo root>"`

   | Exit | Meaning | What you do |
   |---|---|---|
   | 0 | this repo is already in the shape the convention requires | record `applied` with **verify's last line** as the note, verbatim, and go to the next step — **no probe, no dry run, no apply, nothing is mutated** |
   | 3 | not in the target shape, or an assertion failed | continue to sub-step 3 |
   | 2 | the shape is unobservable here, reason on stdout | continue to sub-step 3 |

   Verify first is what stops a repo that did the work by hand — or on the other machine, days ago —
   from being recorded `n/a — does not apply`. The question `verify` answers is *is this repo in the
   target shape*, never *did a migration run here*, and it never exits 1.

   Verify's last line is the note for the same reason apply's is at sub-step 6: in a repo holding the
   work done and uncommitted, that line carries the per-item assertion read out of `HEAD`, and the
   commit this walk hands to `/commit` is what takes that evidence out of `HEAD` for good. A generic
   "already in the target shape" throws away the one run that could ever record it.

3. **Run `probe`:** `python ~/.claude/skills/adopt/steps/<slug>.py probe "<repo root>"`

   | Exit | Meaning | What you do |
   |---|---|---|
   | 1 | does not apply here | record `n/a`, with the reason it printed as the note, verbatim |
   | 2 | cannot tell — it printed the question a human has to answer | go to sub-step 4 |
   | 0 | applies | go to sub-step 5 |
   | 3 | error | stop the run (§4) |

4. **Put the printed question to the user verbatim, and do not answer it yourself.** Show the step's
   text exactly as it printed it — unedited, unsummarised, nothing added but the repo's name if that is
   not already obvious. An exit 2 exists precisely because no file probe can settle it, so a plausible
   answer read off the surrounding repo is the guess
   `~/.claude/memory/feedback_surface_the_gap_dont_fill_it.md` forbids: it would be stored as a
   decision, indistinguishable from a checked one, and never asked again. Their answer maps to one of
   three, and to nothing else:
   - *does not apply here* → record `n/a`, note = their reason in their words
   - *applies, but not doing it* → record `declined`, note = their reason in their words
   - *fixed it by hand* → re-run from sub-step 2, and let `verify` decide rather than the claim

   A question never turns into an `apply`. If the user asks you to make the call for them, say what the
   step can and cannot see and ask again.

5. **Dry run, show, ask — in that order, every time:**
   `python ~/.claude/skills/adopt/steps/<slug>.py apply "<repo root>" --dry-run`
   Show its output in full and ask whether to apply it. **Never run `apply` without a dry run the user
   has seen and agreed to.** A no here is a `declined` line at §3, not a silent skip.

6. **Apply, then verify again:**
   `python ~/.claude/skills/adopt/steps/<slug>.py apply "<repo root>"` — exit 0 is done, exit 3 is
   stopped with every source artifact intact, which is a §4 stop. Then run `verify` again; it must exit
   0. Record `applied` with **apply's last line** — its summary — as the note, verbatim: that sentence
   is where the per-item assertion stays durable once the commit destroys the evidence it read. Show the
   lines above the summary to the user rather than compressing them into the note; a TSV field is one
   line.

7. **Run the step's `## By hand, after the script` checks** and report each result. They are the half
   the script deliberately does not assert, so a recorded note never claims more than was checked.

## 3. Record the line

`python ~/.claude/skills/adopt/conventions.py record "<repo root>" <version> <state> "<note>"`

It refuses to write `applied` unless it runs that step's own `verify` and gets 0, so "the number was
bumped but the work was not done" is unreachable — a refusal is a §4 stop, never something to work
around. It routes a `scope: machine` step to `.claude/conventions.local.tsv` by itself. Pass the note
verbatim from whichever side produced it: `apply`'s summary line, `probe`'s printed reason, or the
user's own words.

## 4. The first failure stops the run

A `verify` exiting 3, an `apply` exiting 3, a `probe` exiting 3, or a `record` refusal ends the walk.
Leave the tree exactly as it is, name the failing items the script printed, and report which versions
were recorded before it. Do not skip the failing step and carry on with the next one: later steps may
depend on it, and a run that steps past a failure leaves a contiguous record claiming a history that did
not happen.

## 5. Hand to /commit

Run `/commit`. One commit for the whole walk, subject:

```
chore(conventions): adopt through vN
```

N is the new `adopted-through` — re-run `conventions.py status` to read it rather than counting the
lines you wrote. The record line and whatever the steps changed in the working tree commit together;
`/commit` is what runs `.claude/commit-checks.sh`, the confidentiality scan and the memo and issue
notices, so nothing here commits directly.

If the record file conflicts on a later pull, both machines appended to a sorted file: keep both lines
and sort by version ascending. That is the whole resolution.

## 6. Close with an audit

`python ~/.claude/skills/adopt/conventions.py audit "<repo root>"`

It re-runs `verify` for every `applied` line and `probe` for every `n/a` one, so an `n/a` that has since
become applicable surfaces as a finding rather than a silence. A `NOT COVERED` line means a retired
script can no longer justify a pass, and a judgement-only step prints `judgement — not re-checkable`.
Report what it prints. A line that now fails is the next task, raised with the user — not something to
fix inside this run, which is already committed.

## Out of scope

- **Never touch another repository.** The session running in a repo is the only one that may commit
  there. A repo found behind is reported, never adopted from here.
- Do not author a new step. That is `references/authoring-a-step.md`, read in the session that is
  changing the convention itself, not in the one adopting it here.
- Do not edit a shipped step's script to make this repo pass. A step that is wrong is corrected by a new
  step carrying `supersedes:`, because a repo already past that version will never re-run it.
- Do not hand-write, reorder or edit a line in either record file — `conventions.py record` is the only
  writer, and it is what ties an `applied` line to a `verify` that passed.
- Do not create the artifact a probe refused to create — an empty `.claude/memos/`, a guessed `LICENSE`,
  an invented `engines.node`. The refusal is the step working correctly.
