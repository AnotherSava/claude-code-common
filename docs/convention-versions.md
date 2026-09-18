# Conventions

Dozens of repos depend on this one: the rules in `claude/CLAUDE.md`, the patterns in `git/gitignore`, the skills and the directory layouts they expect. Changing any of it would normally mean keeping it backwards compatible forever, because a change those repos cannot absorb has no way to reach them.

**Conventions are how a breaking change ships.** When a **convention** changes in a way that breaks backwards compatibility, a numbered **version** is published with it: a folder of prose saying what a repo still in the old shape has to do. Each repo stores the latest version it has adopted, so a repo that has not caught up is visible rather than quietly wrong.

A version is a one-time migration, and running it proves nothing about tomorrow — a repo can drift back out of the shape it moved into. That is what **rules** are for: properties a **checker** re-derives at every commit, from the repo's own commit gate. Rules come in two types:

- **Versioned rules** are introduced by a particular version, and run only where the adopted number is at or above it. A rule introduced by v8 does not run in a repo at v7.
- **Universal rules** are gated by no version, and run in every repo whose gate calls the checker, whatever its number.

## Catching up

A convention changes here, and the change ships with its version folder, committed alongside. Every other repo is now at least one version behind — a fact derived by comparing the number that repo recorded against the newest one here. Three steps close the gap, and none of them run unattended:

1. **The session-start notice says so** in that repo, the next time a session opens there.
2. **You run `/adopt` there.** It walks the pending versions in ascending order, one at a time: reading the version's prose in full, performing the migration where it applies, and advancing the number by one.
3. **`/commit` commits the record with the work.**

No session ever writes to a repo other than its own. `/github-status` reports where every repo stands, across both machines at once, but closing a gap takes a session opened in the repo itself.

## Versions

One number per migration, carried by the folder that holds it — `claude/conventions/versions/NNN-slug/`. That name is the identity, and the number is stored nowhere else, so the two can never disagree.

[What the conventions require](convention-requirements.md) lists the set as it stands — one line per version, and which of them handed a rule to the checker.

A version is warranted on one narrow test: **a repo already conforming to the previous version must now do something.** Doing something is either performing a migration or taking on a rule it was not being checked against before. Rewording a convention without changing what it requires is neither, and ships without a version.

A new rule qualifies even when no repo currently violates it. A versioned rule runs only where the adopted number is at or above the version that introduced it, so one added without a version of its own would sit in the tree enforcing nothing. (Universal rules are the deliberate exception, and the checker's section says what earns that.)

Each version folder holds a `README.md` — a title, optionally the rules it introduces, then four sections:

| Section | Holds |
|---|---|
| `## What changed` | the convention as it now reads, and why it moved |
| `## Migrating an existing repo` | what an already-conforming repo has to do — the files, the transformation, what to check afterwards |
| `## When it does not apply` | the conditions that make the migration a no-op here, each with the positive evidence that settles it |
| `## Continuing rule` | the rule handed to the checker, named — or the words `None — this is a one-time migration.` |

The third section names its evidence rather than its conclusion, so "nothing found" stays distinguishable from "nothing looked at". The default is prose an agent follows; a version carries a script beside it only where the migration is mechanical and tedious.

## Changing a convention

Versions and rules answer different questions. A version answers *did this migration run here* — a fact about the past, which stays true. A rule answers *is this repo in that shape now* — an answer that expires at the next commit, because the next commit can add the file the rule forbids.

That difference decides where each one lives. A version folder is frozen the moment any repo runs it: editing it would give two repos different behaviour under one number, and the earlier one will never re-run it to find out. A rule is the opposite — a better way of spotting the same violation should reach every repo at once.

So a **stricter** rule is a new version and a **better-detecting** rule is an edit to the rule file. The first changes what a repo is required to be, and a repo takes that on by adopting, never because someone edited a shared file under it. The second changes only how accurately the requirement is measured, so there is nothing for the repo to decide.

## The record

One file, `.claude/conventions` under the repo's own `.claude/`, committed: a comment block and exactly one line of content, holding the highest version this repo has adopted. In full:

```
# Convention version this repo has adopted, from the claude dotfiles repo.
# Written by /adopt. See claude/conventions/ in that repo.
9
```

The content line is a non-negative integer, or the word `exempt` and a reason. Anything else is a parse error naming the file and what it found.

**A repo with no file at all is at 0 and has never been asked**, which is a different fact from being at 0, and the notice words the two differently.

`/adopt` is the only thing that writes the line. It refuses to lower the number, to exceed the newest version in this checkout, or to skip — the new number must be the current one plus one, so the record can never claim a migration nobody read.

## The checker

The checker is what makes a rule continuous. It reads a repo's number, runs every rule that number entitles it to, and reports anything it could not measure rather than passing it. A repo starts calling it by adopting v9, whose migration adds one line to `.claude/commit-checks.sh`:

```
python ~/.claude/conventions/check.py .
```

**There is one copy of it per machine, not one per repo.** `~/.claude/conventions` is a symlink to this repo's `claude/conventions/`, so every repo's gate reaches the same file and pulling this repo updates the checker everywhere at once.

Each rule is one file — under `claude/conventions/rules/` when a version introduces it, under `claude/conventions/universal/` when nothing does. Rules detect and never mutate. A rule that cannot establish its answer raises rather than returning nothing: it reports **UNMEASURED** and fails the gate, because a rule that could not look must never read as a rule that passed.

### Universal rules

A rule gated by no version runs in every repo whose gate calls the checker, whatever its number, and fails that gate exactly as a versioned rule does. It needs no adoption of its own — but it still needs the gate, which arrives with v9, so a repo that has never adopted runs no rules at all. It has no version README behind it, so it carries its own repair command and prints it under the finding.

That reach is the cost: a universal rule arrives everywhere with no adoption in between. **A property a repo can adopt belongs in a version.** Only a property no migration could settle belongs here, and both of today's are the same shape — a link this machine either made or did not, which no number could ever be true of because the same repo arrives on the second machine with the work genuinely not done.

- **`memory-cache-linked`** — this machine's Claude memory cache for the repo is a link into the repo's committed `.claude/memory/`. A repo with no `.claude/memory/` holds vacuously: with nothing committed there is nothing to point at, and whether a repo keeps project memory is not a machine's question.
- **`install-links-present`** — every symlink and git setting the install blocks create is in place, with the platform's own README block as the repair.

## The session-start notice

A `SessionStart` hook compares the newest version in this checkout against the one the repo has recorded, and says nothing when they agree. It verifies nothing and forks no subprocess.

```
Conventions in this repo are 5 versions behind (at v4, latest is v9, dotfiles at bd4bd9b).
  - v5   The Node toolchain is declared, enforced and pinned
  - v6   A LICENSE file sits at the repo root
  - v7   The docs theme is pinned to a tag
  - v8   Compose services carry the project's name
  - v9   The commit gate runs what the deploy runs, and the conventions checker
Run /adopt to catch up.
```

Every message claiming a "latest" version names the dotfiles short sha, because the two machines routinely sit at different commits and a behind checkout reporting a repo as current is the one wrong answer this system must not give.

Silence means the repo is current, its origin belongs to someone else, its record reads `exempt` — or the install is broken, which `python ~/.claude/hooks/check-install.py` tells apart.

## Adopting

Run `/adopt` in the repo that is behind, from that repo's own session. Commit or stash what you have first: the walk does not commit, but it hands to `/commit`, and a tree already carrying unrelated work makes that commit harder to review. A dirty tree is not a gate — several repos hold a convention's work already done and never committed, and the record and that pending change commit together.

The walk takes the pending versions in ascending order, one at a time:

1. **It reads the README in full** before touching anything.
2. **It checks the "When it does not apply" conditions against this repo**, settling each with the positive evidence the README names. A version that does not apply here is still decided: the number advances with nothing mutated.
3. **Otherwise it performs the migration**, showing every mutation before it happens and applying it only on a yes.
4. **A question the README puts to a human reaches you verbatim** — whether a repo wants a backlog at all, whether a missing LICENSE is deliberate. The agent does not answer those on your behalf.
5. **It checks whatever the README says to check afterwards.**
6. **It advances the record by one.**

Then the next version. The number moving one at a time is what makes an interrupted walk safe: a run that stops partway loses nothing, and the next `/adopt` resumes at the first pending version.

The walk ends with one commit:

```
chore(conventions): adopt through vN
```

### Where a walk stops before it starts

Three of them are permanent — a repo in any of these states records nothing at all, and the session-start notice stays silent there:

- **There is no git repo here.** A record in an untracked directory is a file no clone ever sees.
- **The origin belongs to someone else.** Ownership is read from the origin URL against one hardcoded account name, and a third-party clone adopts nothing. A repo with no origin is *not* third-party and does adopt.
- **The record reads `exempt`.** A repo that must never adopt carries `exempt` and a mandatory reason in place of a number — the one content line written by hand, and it travels with the repo, because an exemption is the repo's rather than one machine's.

Two are temporary, and naming what to fix is the whole of the answer:

- **The repo or the dotfiles checkout is behind its upstream.** Pull first, or the walk reasons from a stale version set.
- **The record file is ignored**, so it would never travel. Fix the `.gitignore` first.

An exempt repo still runs every universal rule, which is the part an exemption cannot reach: it is a statement about the sequence, and those are gated by no number in it.

## Where repos stand

The CONV column of `/github-status` carries every repo's number for both machines at once, and a repo with a clean tree, nothing unpushed and no open issues still appears there on the strength of its convention gap alone.

## The boundary of the system

**Every versionable convention has been decided here** — not that everything in `claude/CLAUDE.md` is satisfied. Some conventions can never carry a version at all: agent behaviour that leaves nothing on disk, properties of source code rather than of repo shape, and facts about a machine rather than a repo. `claude/conventions/not-versioned.md` names each one with its reason, so that a convention belonging to neither that file nor the version set reads as a gap to close rather than a silence to read past.

## Where each piece lives

| Piece | Path |
|---|---|
| What the set requires today | [`docs/convention-requirements.md`](convention-requirements.md) |
| The versions | [`claude/conventions/versions/`](../claude/conventions/versions/) |
| The rules, and the universal ones | [`rules/`](../claude/conventions/rules/) · [`universal/`](../claude/conventions/universal/) |
| The checker a commit gate runs | [`claude/conventions/check.py`](../claude/conventions/check.py) |
| The contract for writing a version or rule | [`claude/conventions/authoring.md`](../claude/conventions/authoring.md) |
| The walk procedure | [`claude/skills/adopt/SKILL.md`](../claude/skills/adopt/SKILL.md) |
| A repo's own record | `<repo>/.claude/conventions` |
