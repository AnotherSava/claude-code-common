# Convention versions

A convention in this repo is a claim about every repo on the machine. A rule in `claude/CLAUDE.md`, a pattern in `git/gitignore`, a directory layout a skill expects — change one and every other repo is left in the old shape, with nothing anywhere saying so. The first such change made by hand missed one repo entirely and left five more holding the work uncommitted.

A convention change splits in two, and the halves are kept apart on purpose. What a repo has to do **once** — move a file, add a field, rename a service — ships as a numbered **version**: one folder of prose, committed alongside the change that caused it, written as instructions an agent follows in the repo that is behind. What has to hold **continuously** — that the field is still there, that the next service added does not take a generic name — ships as a **rule**, and the rule is run by a checker every repo's commit gate calls.

A repo's state is one integer: the highest version it has adopted. A session-start notice prints the gap, `/adopt` walks it, `/commit` commits the result, and the checker keeps the rules holding from then on.

This page describes that system end to end — the version, the record, the checker and the two kinds of rule it runs, and what "current" does and does not mean. The agent-facing procedure lives elsewhere; the last section names the file for every piece.

## The loop

1. **A convention changes in this repo**, and the change ships with its version folder, committed alongside.
2. **Every other repo is now one version behind** — a fact derived from two integers, not stored anywhere.
3. **The session-start notice says so**, in that repo, on screen.
4. **Someone runs `/adopt` there**, in that repo's own session. It walks the pending versions in ascending order, one at a time: the version's prose is read in full, the migration is performed where it applies, and the number advances by exactly one.
5. **`/commit` commits the record with the work**, one commit for the whole walk.

Nothing in that loop runs unattended, and nothing reaches across repos. A repo found behind is reported; closing the gap is a walk through that repo's own session.

The continuing half has no loop. A version that introduces a rule hands it to the checker, and from the moment that version is adopted the repo's own commit gate runs it — so the property is asserted at every commit rather than sampled whenever somebody remembers to go and look. A second, smaller class of rule is gated by no version at all and runs in every repo the moment it is committed here; the checker's section below says what belongs there and what it costs.

## What a version is

A monotonic integer, one per migration, carried by the folder that holds it — `claude/conventions/versions/NNN-slug/`, the number zero-padded to three digits. That name is the identity, and the number is stored nowhere else, so the two can never disagree. A migration sequence is the one ordering in these repos that sits in a filename rather than in a field, because the number is what a repo's record names and what someone reads back months later: it identifies a migration rather than sorting one.

**The sequence was renumbered once, on 2026-09-16**, when the memory-cache migration stopped being a version at all and became the first universal rule. Every number above it moved down one — what were v5 through v15 are now v4 through v14 — and every record naming one of them was rewritten by hand, since nothing can tell a record reading v9 back when it meant `package-manager-pin` from one reading v9 now that it means `license-file-present`. A number written down before that date therefore names a migration that carries the number one below it today — old v9 is this set's v8 — so a commit message, a memo or a transcript older than the change has to be read against the sequence it was written in. Treat that as the price of retiring a version, not as something the sequence does — the numbers are stable in every other respect, and the alternative, a hole in the sequence, is refused by the loader that derives `latest` from it.

A version is warranted on one narrow test: **a repo already conforming to the previous version must now do something.** Doing something is either performing a migration or taking on a rule it was not being checked against before. A rewording qualifies as neither. A new continuous rule does qualify even when no repo currently violates it, because a rule runs only where the adopted number is at or above the version that introduced it — shipped without a version of its own, it would be enforced nowhere.

Each version folder holds a `README.md` opening with frontmatter:

```yaml
---
title: The Node engines range is declared
affects: memo        # optional, comma-separated: tools whose stored data this reshapes
rules: node-engines  # optional, comma-separated: continuing rules this version introduces
---
```

Those three are the whole of it, and a fourth key is refused rather than ignored: a field left behind by a port would otherwise sit there reading as authoritative while the folder name and the folder's contents quietly decided everything.

Then four mandatory sections, in this order, and nothing else at that level:

| Section | Holds |
|---|---|
| `## What changed` | the convention as it now reads, and why it moved |
| `## Migrating an existing repo` | what an already-conforming repo has to do — the files, the transformation, what to check afterwards |
| `## When it does not apply` | the conditions that make the migration a no-op here, each with the positive evidence that settles it |
| `## Continuing rule` | the rule handed to the checker, named — or the words `None — this is a one-time migration.` |

"Nothing found" has to be distinguishable from "nothing looked at", which is why the third section names its evidence rather than its conclusion. The default is prose and nothing else: a version may carry an `apply.py` beside its README where the migration is genuinely mechanical and tedious, and that script takes the repo root, does the work, prints what it did, and exits non-zero on any line it cannot classify.

The optional `affects: <tool>` names a tool whose stored data this version reshapes, so that tool can refuse to read a format the repo has not adopted yet. The memo backlog is the first: `/memo` asks the adopted version rather than looking for the file the migration replaces, so the next format change needs no edit there.

To see the live set:

```
python ~/.claude/conventions/engine.py versions
```

which prints one line per version with its number, slug, title and the rules it introduces. What they cover, in groups: the `.claude/` plumbing every project carries (the memo backlog and the shape of the memory files), what a project `.gitignore` may and may not hide, line-ending normalization for encrypted paths, the Node toolchain chain (declare an engines range, enforce it, pin the package manager), a LICENSE at the root, a pinned docs theme, service naming on the shared host, a commit gate that runs what the deploy runs, and that gate calling the checker so the continuing rules run at all.

## Why a version is a migration and a continuing rule is not

The two answer different questions. A version answers *did this repo change shape* — asked once, and the answer never expires. A rule answers *is this repo in that shape now* — an answer that expires at the next commit, because the next commit can add the file the rule forbids.

That difference decides where each one lives, and they cannot share a home. A version folder is frozen the moment any repo runs it: editing it would give two repos different behaviour under one number, and the earlier one will never re-run it to find out. A check is the opposite — a better way of spotting the same violation should reach every repo at once, including the ones that adopted years of versions ago.

So a **stricter** rule is a new version and a **better-detecting** rule is an edit to the rule file. The first changes what a repo is required to be, and a repo takes that on by adopting, never because someone edited a shared file under it. The second changes only how accurately the requirement is measured — the repo was mismeasured rather than changed, so there is nothing for it to decide.

It also settles what the record does not have to hold. A per-repo state saying "this convention does not apply to me" is an exception remembered once in a file nobody re-reads; the same exception written into the rule is evaluated against the repo in front of it every time. And a state saying "it applies and we chose not to" lets an underspecified convention sit there while the repos around it drift — the useful response to a refusal is to fix the convention, not to record the refusal. What is left is one number, and a number is exactly the shape of *how far a sequence of migrations has run*.

## The record

One file, `.claude/conventions` under the repo's own `.claude/`, committed: a comment block and exactly one line of content, holding the highest version this repo has adopted. In full:

```
# Convention version this repo has adopted, from the claude dotfiles repo.
# Written by /adopt. See claude/conventions/ in that repo.
14
```

The content line is a non-negative integer, or the word `exempt` and a reason. Anything else is a parse error naming the file and what it found, and the comments above it are the file's own statement of what its one line means — a bump keeps whatever comments are already there rather than regenerating them.

**A repo with no file at all is at 0 and has never been asked**, which is a different fact from being at 0, and the notice words the two differently. Nothing is ever assumed decided by omission.

One command writes it, and it is the only thing that does:

```
python ~/.claude/conventions/engine.py adopt "<repo root>" <n>
```

It refuses to lower the number, refuses a number above the newest version in this dotfiles checkout, and refuses to skip — the new number must be the current one plus one. Advancing one at a time is what keeps the record from claiming a migration nobody read: a walk that jumped straight to the newest number would leave every version under it recorded as run on the strength of nothing.

### One file, not two

A second record used to sit beside it: `.claude/conventions.local`, gitignored, holding the highest *machine-scoped* version wired on this machine. One version in the set needed it — the one asserting that the machine-local memory cache is a link into the committed `.claude/memory/` — because no repo can carry a per-machine symlink, so a version declaring `scope: machine` was written to both files and the two numbers said different things.

That half is gone, and with it the `scope:` field, the second file, and every function that read one. The reason is that what it recorded was never a migration. A migration ran or it did not, and the answer never expires; the link is per-machine, so a second machine holds the repo with the work genuinely not done, and it can break years after any adoption — a cleared cache, a moved checkout, a Git Bash `ln -s` that made a copy. No single number could be true of that, which is exactly what the machine record kept trying to be. It is a universal rule now, re-derived at every commit rather than remembered once, and a repo's whole convention state is one integer in one tracked file that a clone carries intact.

## The checker

What a repo's `.claude/commit-checks.sh` runs:

```
python ~/.claude/conventions/check.py "<repo root>"
```

It reads the repo's adopted integer and runs every rule that a version at or below that number introduced, plus every universal rule, which no number gates. A rule introduced by v11 does not run in a repo at v10. The mapping from a rule to the version that introduced it is derived from the versions' `rules:` frontmatter, so nothing states it twice; a rule file no version names, and a named rule with no file, both fail the tests below.

Each rule is one file — under `claude/conventions/rules/` when a version introduces it, under `claude/conventions/universal/` when nothing does — exposing a single function that takes the repo root and returns one human-readable line per violation, an empty list meaning the rule holds. Rules detect and never mutate.

A clean run says what it checked rather than leaving it to the silence:

```
conventions check: <repo root>
adopted v14, dotfiles at bd4bd9b — 9 rule(s) taken on, 1 universal

all 10 rule(s) held: gitignore-unhides-committed, gitignore-scope-global, memory-file-shape, …
```

The two counts in that header are kept apart because they are answers to different questions: what this repo took on by adopting, and what runs here whatever it adopted. A failing run prints a heading per rule — `<name> (v7)` or `<name> (universal)` — with its violations under it, the rule's `fix:` line under those when it names one, then a tally. Three details decide whether that output can be trusted:

- **A rule that cannot establish its answer raises rather than returning nothing.** Git refusing, a file that will not read, a bug in the rule itself: it is reported as **UNMEASURED**, named, with its traceback, and the run exits non-zero. A rule that could not look must never read as a rule that passed.
- **A run that checked nothing says so** — "nothing was checked" rather than a clean bill, so "checked and clean" and "checked nothing" cannot be read off the same empty output. It takes both halves being empty: a repo that has adopted no rule-bearing version still runs every universal rule, and only a checkout holding none of those reaches that sentence.
- **Exit codes are the same three the engine uses:** `0` everything held · `1` a rule was violated or went unmeasured · `2` the tool refuses and a human has to fix something — a bad invocation, an unreadable record, a version set that will not load.

Two things every rule has to get right, both paid for once already and both in the shared helper beside them. It has to **ask git what it hides**, because a `package.json` inside a gitignored `venv/` or a scratch `tmp/` is not a manifest anyone maintains — consulting the index as well, so a force-added file inside an ignored directory still counts. And any git exit that is neither "ignored" nor "not ignored" means the question went unanswered, so the rule raises and the run reports it unmeasured instead of treating silence as a pass.

The rules and the version set have their own tests, which are what a change to either has to pass before it is committed here:

```
python claude/conventions/tests.py
```

They assert that every version folder parses and the numbers are contiguous, that all four mandatory sections are present, that versioned rules and versions name each other in both directions, and that the universal ones are wired the mirror image of that: no version claims to introduce one, no filename sits in both directories, and each names a `FIX`. Then they run every rule against a tree built in a temp directory by the test itself — empty on a conforming tree, non-empty on a violating one, and for the memory-cache rule the round trip runs the very script its `FIX` names and checks the finding goes away, so two independent derivations of the cache directory's name have to agree rather than one agreeing with itself. Each rule raises rather than passing when git cannot answer, and the record refuses to be lowered, skipped or pushed above the newest version.

### The universal rules

A rule under `claude/conventions/universal/` is gated by nothing. It runs in every repo whatever its number — one at v0, one exempt from the sequence entirely — from the moment it is committed here, and it fails a commit gate exactly as a versioned rule does: the same heading, the same tally, the same exit code 1. The label under which it reports is the only difference a reader sees — `(universal)` where a versioned rule carries the number that introduced it.

Two things follow from having no version behind it. There is no README a repo was ever walked through, so each universal rule names its own remedy: a module-level `FIX` constant holding the command that repairs what it found, printed under the finding rather than in a summary further down. And there is no frontmatter its filename has to appear in — the directory *is* the list, read at every run, so a file dropped in there runs rather than sitting inert waiting to be named somewhere.

That reach is why this is the smaller class on purpose. A universal rule arrives in every repo on the machine with no adoption in between, which is the thing the numbered half exists to prevent, so **a property a repo can adopt belongs in a version.** What belongs here is a property no migration could settle for good, because it is not about the repo alone.

Both rules that meet that test today assert a link this machine either made or did not. The `memory-cache-linked` rule asserts that this machine's Claude memory cache for the repo is a link into the repo's committed `.claude/memory/`, and recommends `bash ~/.claude/scripts/link-project-memory.sh`. It was a version until 2026-09-16, and it stopped being one for the reason the second record file stopped existing: the link is per-machine, a second machine holds the repo with it not made, and a cleared cache or a Git Bash `ln -s` that quietly made a copy breaks it long after any adoption. A repo with no `.claude/memory/` holds vacuously — the convention points the cache at a committed directory, and with none there is nothing to point at — which is evidence read off the repo rather than an absence inferred from the machine. Nothing here ever creates one: whether a repo keeps project memory at all is not a machine's question.

The `install-links-present` rule asserts that every symlink and git setting the install blocks create is in place, and names the platform's own block in the README as the repair. It reads `check-install.py`'s lists and its `samefile` comparison rather than restating either, because a contract with three copies has already drifted once. What makes it universal is what makes the other one universal — a fresh machine has none of these links, and a `ln -s` from Git Bash leaves a copy that every textual check calls healthy. What puts it in a *commit* gate is v14: telling every repo to run `python3 ~/.claude/conventions/check.py .` made the gate itself reach through one of these links, and the session-start check that used to be the only assertion has already run by the time anyone commits — so a link arriving in a mid-session `git pull` is missing and silent for the rest of that session. The one link it cannot vouch for is the one it was invoked through, which needs no vouching: the gate line could not have run without it.

## The session-start notice

A `SessionStart` hook compares two integers: the newest version in this dotfiles checkout, and the one the current repo has recorded. It says nothing when they agree. It verifies nothing and forks no subprocess; re-deriving even one rule at session start would cost an order of magnitude more than the whole hook budget.

What it prints, when it prints:

```
Conventions in this repo are 8 versions behind (at v6, latest is v14, dotfiles at bd4bd9b).
  - v7   The engines range is enforced, not advisory
  - v8   The npm version is pinned in package.json
  - v9   A LICENSE file sits at the repo root
  - v10  The docs theme is pinned to a tag
  - v11  Compose services carry the project's name
  - ... 3 more
Run /adopt to catch up.
```

Five bullets and a count, because a line per pending version at every session start is a wall nobody reads. Other things it can say, each for its own condition: that this repo has no record at all and should record where it stands; that the repo records a version newer than this checkout has, so the *dotfiles* need pulling (the `/adopt` offer is withheld rather than qualified); that the record could not be parsed and `/adopt` will not run until it is fixed; that the version set itself could not be read; or that conventions cannot be recorded here because this is not a git repo.

Two details worth knowing:

- **Every message that claims a "latest" version names the dotfiles short sha**, because the two machines routinely sit at different commits and a behind checkout reporting a repo as current is the one wrong answer this system must not give. The diagnostic messages, which claim no latest, carry no sha.
- **The message is a `systemMessage`** — it reaches the screen and never the transcript, so pasting it into chat buys nothing. Running `/adopt` re-derives the gap itself.

Silence has four causes and only one of them is a problem: the repo is current, the origin belongs to someone else, the record reads `exempt` — or the install is broken. A `~/.claude/hooks` that is a copy rather than a symlink (what Git Bash `ln -s` leaves behind on Windows) freezes the notice forever with nothing appearing wrong. Telling those apart is what `python ~/.claude/hooks/check-install.py` is for.

## Running `/adopt`

Run it in the repo that is behind, from that repo's own session. It gathers its own context first — the repo root, whether either checkout is behind its upstream, whether the record file is ignored, the install check, and the conventions status — then walks the pending versions in ascending order, one at a time.

For each version the shape is fixed:

1. **Its README is read in full**, before anything is touched.
2. **The "When it does not apply" conditions are checked against this repo**, and each one is settled by the positive evidence the README names. A version that does not apply here is still decided: the number advances with nothing mutated.
3. **Otherwise the migration is performed** as the README instructs, and every mutation is shown before it happens and applied only on a yes.
4. **A question the README puts to a human goes to you verbatim.** Some conventions contain a clause no file can answer — whether a repo wants a backlog at all, whether a missing LICENSE is deliberate — and the agent does not answer those on your behalf.
5. **What the README says to check afterwards is checked**, and where the version introduces a rule, the checker is the thing that confirms it.
6. **The record advances by one**, through the adopt command, which is the only writer of that file.

Then the next version. The number moving one at a time is what makes an interrupted walk safe: the record is rewritten after each version, so a run that stops partway loses nothing and the next `/adopt` resumes at the first pending version.

### What stops a run

- **The repo or the dotfiles checkout is behind its upstream.** A migration that deletes a file the other machine just appended to merges cleanly and loses the append in silence; a stale version set records this repo as current against a `latest` that has already moved.
- **The record file is ignored**, so it would never travel. Fixing the `.gitignore` comes first.
- **There is no git repo here.** A record written in an untracked directory is a file no clone ever sees.
- **A version fails** — a migration that cannot be completed, or the engine refusing to record. The walk ends there rather than skipping ahead, because a later version may depend on what an earlier one did, and a run that steps past a failure leaves a number claiming a history that did not happen.

**A dirty working tree is deliberately not a gate.** Uncommitted work is the common case — several repos hold a convention's work already done and never committed — and the record and that pending change commit together.

The walk does not commit. It hands to `/commit`, which produces one commit for the whole thing:

```
chore(conventions): adopt through vN
```

## Reading where a repo stands

```
python ~/.claude/conventions/engine.py status "<repo root>"
```

```
repo: <repo root>
latest v14 (dotfiles at bd4bd9b)
this repo: v10
4 version(s) pending
  v11  cotenant-service-names       Compose services carry the project's name  [rules: cotenant-service-names]
  v12  commit-checks                A commit gate runs what the deploy runs
  v13  memos-done-dated             Addressed memos carry their close date at the front of the name
  v14  gate-runs-the-checker        The commit gate runs the conventions checker
```

The path argument is any repo, so this inventories another checkout without opening a session in it. It exits 0 when it can answer — being behind is the normal answer, not a failure — and 2 when it refuses: not a git repo, an origin owned by someone else, a record it cannot parse.

For whether a repo is *still* in the shape its number claims, the question goes to the checker rather than here, and the answer is re-derived at every commit rather than on request.

Across every repo at once, the CONV column of `/github-status` carries the same number for both machines, and a repo with a clean tree, nothing unpushed and no open issues still appears in that report on the strength of its convention gap alone.

## What "current" means

**Every versionable convention has been decided here** — not that everything in `claude/CLAUDE.md` is satisfied.

The difference is deliberate and it is written down. Four kinds of convention can never carry a version, and `claude/conventions/not-versioned.md` enumerates every one of them with its reason:

- **Agent behaviour** — how the assistant works, not how a repo is arranged. Nothing on disk differs between a session that followed the rule and one that broke it.
- **Code content** — properties of the source rather than of the repo's shape. A linter or a review enforces these line by line; a migration cannot, because the target shape includes every line not yet written.
- **An unbounded property** — true of an open, growing set, so one pass proves nothing about the next commit. This is the one boundary the checker moved: an unbounded property that a rule *can* re-derive belongs to the checker, which asserts it at every commit, and only what no rule can express stays out of the system entirely.
- **Global, not per-repo** — one fact about this machine or this checkout. Recording it per repo would be one answer copied everywhere, and the checkable ones already belong to `check-install.py`. A fact about this machine's relationship to *one* repo is a different thing again, and that is what a universal rule is for.

A convention in neither that file nor the version set is a gap to close, not a silence to read past. Without that boundary written down, a current record would read as a clean bill of health for the entire guidelines file.

## Repos outside the system

Three ways a repo records nothing, and they are not interchangeable:

- **Someone else's project.** Ownership is read from the origin URL and compared against one hardcoded account name. A clone of a third-party repo adopts nothing and the notice stays silent there. A repo with no origin at all is *not* third-party and does adopt.
- **Exempt.** A repo that must never adopt carries `exempt` and a reason on the content line, in place of a number. The reason is mandatory; a bare `exempt` is a parse error. This is the one content line written by hand rather than by the adopt command, and it travels with the repo like any other — an exemption is the repo's, not one machine's.
- **Not a git repo.** Nothing can be recorded, and the notice says so where a `.claude/` directory or a `CLAUDE.md` is present. A scratch directory with neither stays quiet.

An exempt repo runs no *versioned* rules, and the checker's header says which of the two it is reporting — exempt with its reason, or a repo that has adopted nothing. The universal rules still run there, which is the part an exemption cannot reach: it is a statement about the sequence, and those are gated by no number in it.

## Changing your mind

- **There is no state for a refusal.** Declining a migration leaves the repo at the version below it and the notice keeps saying so, which is the intended pressure: a convention several repos refuse is a convention that is wrong, or one whose "When it does not apply" section is missing a condition. Both of those are fixed in the version set, where the fix reaches every repo, rather than recorded once per repo.
- **Undoing an adoption is a revert, not an `unapply`.** No version defines an inverse. Since the record and the migration commit together, reverting the walk's commit undoes both, the record included: it is one tracked file, so nothing survives the revert still claiming a number the tree no longer earns. The revert is the mechanism because the engine refuses to lower a number on its own.
- **Reversing a convention outright is a later version**, whose README says what it reverses and why. The number advances either way: a shipped version is never edited to change its behaviour, because a repo already past it will never re-run it, and a repo that never got to the original simply runs the pair back to back.
- **Loosening a rule is an edit to the rule**, not a version — a repo being asked for less does not have to decide anything. Tightening one is a version, for the same reason in reverse.

## When something goes wrong

- **The record will not parse.** One bad line reaches five surfaces at once: `/adopt` refuses to run, the notice says the state is unknown, `/github-status` shows `?` with the reason, the commit gate's checker exits 2 rather than reporting a clean run — and `/memo` says so on stderr and proceeds, since a backlog helper that refuses because a sibling tool is broken is worse than the thing it would be preventing. Repairing the file by hand to a parseable state is the escape hatch; the ordinary rule against hand-editing it assumes a file the engine can still read.
- **The record conflicts on a pull.** One line, two numbers, and the higher one is right only if the work under it is in the tree you now hold. Since the migration and the record commit together, a merge that brought both keeps the higher number — then run the checker to confirm. A merge that resolved the migration's own files the other way needs the lower number put back and that stretch re-walked.
- **`/memo` refuses in a repo that has never adopted.** That is intended, and it is the first thing a fresh install runs into: the memo commands read a layout a version defines, so a repo at v0 is a repo whose backlog format is unknown rather than known-fine. Run `/adopt` there once.
- **A rule reports `UNMEASURED`.** Neither a pass nor a failure: something stopped it from looking. The named exception says what — most often git refusing to answer in a directory that is not the repo it was pointed at. It fails the gate on purpose, because the alternative is a commit check that goes quiet exactly when it cannot see.
- **The notice never appears anywhere.** Check the install before concluding the repos are current.

## Setting this up in a fork

Three things the system needs. Only the second announces itself — `check-install.py` fails the `~/.gitignore` link and the `core.excludesFile` setting at every session start, and `/adopt` repeats its FAIL lines — while the other two are silent:

1. **Change the owner.** The account name that decides "my repo" versus "someone else's clone" is a constant in `claude/conventions/engine.py`. Leave it as shipped and every repo you own reads as third-party: the notice is silent, `status` says it adopts nothing, the adopt command refuses, and every tool that asks whether a repo is behind is waved through — indistinguishable from being current.
2. **Install the global excludes file.** The `gitignore-scope-global` rule compares every committed `.gitignore` against it, located through `git config --global core.excludesfile` rather than assumed to be `~/.gitignore`. Skip that half of the install and there is no second side to compare against, so the rule raises rather than reporting a repo full of duplicates as clean — which means every commit in every repo that has adopted it reports UNMEASURED until the setting is there. The [Global Installation](../README.md#global-installation) section of the README has the commands.
3. **Have Python 3.10 or newer on PATH.** The engine is standard library only, with nothing to install, but it uses syntax 3.9 rejects at import — and the session-start notice swallows that failure into silence rather than a traceback.

## Where each piece lives

| Piece | Path |
|---|---|
| The rule, injected into every session | the Convention Versions section of [`claude/CLAUDE.md`](../claude/CLAUDE.md) |
| The versions | [`claude/conventions/versions/`](../claude/conventions/versions/) |
| The engine — the version set, the record, status | [`claude/conventions/engine.py`](../claude/conventions/engine.py) |
| The checker a commit gate runs | [`claude/conventions/check.py`](../claude/conventions/check.py) |
| The continuing rules a version introduces | [`claude/conventions/rules/`](../claude/conventions/rules/) |
| The universal rules, gated by no version | [`claude/conventions/universal/`](../claude/conventions/universal/) |
| The tests a change to either has to pass | [`claude/conventions/tests.py`](../claude/conventions/tests.py) |
| The contract for writing a new version or rule | [`claude/conventions/authoring.md`](../claude/conventions/authoring.md) |
| The walk procedure | [`claude/skills/adopt/SKILL.md`](../claude/skills/adopt/SKILL.md) |
| What can never carry a version | [`claude/conventions/not-versioned.md`](../claude/conventions/not-versioned.md) |
| The session-start notice | [`claude/hooks/conventions-check.py`](../claude/hooks/conventions-check.py) |
| A repo's own record | `<repo>/.claude/conventions` |
