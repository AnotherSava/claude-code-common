---
title: A project .gitignore hides only what is this repo's to hide
rules: gitignore-unhides-committed, gitignore-scope-global
---

## What changed

A project `.gitignore` gets two things wrong in opposite directions, and both are silent.

**It hides files meant to travel with the repo.** Several paths in this system are committed on
purpose: `.claude/settings.json`, `.claude/memory/`, `.claude/memos/`, `.claude/conventions` and
`config/publish.env`. A rule covering any of them makes that file silently never stage — `git add`
is quiet, `git status` shows no untracked entry — and the loss surfaces on the other machine as a
file that was never there. The `config/publish.env` case is the one already paid for: keeping it
ignored meant each machine held its own hand-edited copy, and those copies drifted until one named a
compose service that had not existed for six days. This half comes before every later version that
writes into `.claude/`, because a record written into a hidden directory is a record nobody can
commit.

**It repeats rules that belong to the machine.** An ignore rule for a user-specific artifact — an
IDE folder, an OS cache, a per-machine wrapper a personal skill writes — belongs in the global
excludes file, where one line covers every repo. A copy inside a project file buys nothing and costs
twice: it puts a machine-local detail in a file every contributor reads, and it is a second copy
that drifts, so a repo keeping its own `config/deploy.env` line goes on enforcing a rule the global
file may have moved past. The global file is located through `git config --global
core.excludesfile`, never assumed to be `~/.gitignore` — this machine's setting is the literal
string `~/.gitignore`, which no `open()` resolves, so anything that hard-coded the path *and*
skipped `expanduser` would happen to work here and fail the moment either changed.

Two kinds of line go under the second half, and nothing else does: a **duplicate** — the same entry,
after stripping a leading `**/`, appears in the global file, and either the `.gitignore` sits at the
repo root or the pattern floats — and a **bare `scripts/` line**, which supersedes the global file's
root-anchored wrapper entries with a pattern matching at any depth, hiding the repo's own committed
scripts as well. One repo tracks `scripts/package.ts` under exactly such a line.

**Anchoring is out of scope, deliberately.** CLAUDE.md asks a project pattern to carry a leading
slash "unless matching at any depth is intended", and that clause makes the question undecidable
from the file alone: the fleet holds eleven floating patterns — `data/`, `backup/`, `cities/`,
`.wrangler/` and the rest — each plausibly written that way on purpose. Asserting anchoring would
report all eleven and be right about none.

## Migrating an existing repo

**The prerequisite is the set of `.gitignore` files this repo commits.** Read it from
`git ls-files`, never from a directory walk: a virtualenv, a build directory and an IDE each write a
`.gitignore` of their own — the fleet holds nine, under `.venv/`, `.next/` and `.idea/` — and
rewriting one of those would be editing something the repo neither owns nor keeps. That same set
feeds both passes below.

Fetch first, and do not run this on a branch behind its upstream. Both passes rewrite a committed
file the other machine may have edited, and a line changed here merges cleanly against a line added
there, losing it without a conflict.

### Pass 1 — unhide what must stay committed

There is work here when a rule in one of those files makes git hide at least one required path.

Put the question to `git check-ignore` rather than answering it by reading the file, so a pattern
reaching a path by a route nobody predicted — `**/config/*.env` over `config/publish.env` — is
caught as readily as one naming it outright. Two flags decide what the answer means:

- The plain form is what says "ignored". The `-v` form exits 0 on a *negation* as well, because its
  status answers "did any pattern apply" and a `!` rule applies as much as an exclusion does.
  Reading that status as a verdict gets the answer backwards on exactly the paths a negation exists
  to protect. Use `-v` to find the file and line behind a hit, never to decide whether there was one.
- Pass `--no-index` on every call. By default the command consults the index and calls a *tracked*
  path not ignored whatever the rules say, so a repo that once force-added a file it excludes would
  answer "no deviation" while the rule still hides every new file beside it.

Then delete the offending rule, or re-include the path below it where the rest of the pattern is
still wanted.

### Pass 2 — drop lines that belong to the global file

There is work here when one of those files holds a duplicate line or a bare `scripts/` line.

The anchoring clause is what keeps a nested file safe. A `config/deploy.env` line in
`web/.gitignore` is anchored to `web/` and hides `web/config/deploy.env`, which the global entry —
anchored to each repo's root — never reaches, so it is not the same rule and it stays. A floating
pattern like `.DS_Store` matches at any depth wherever it is written, so the nested copy really is
redundant and goes.

Leave one entry out of the comparison on purpose. The global file carries `.env`, and so do three
project files — but CLAUDE.md names `.env` among the things *every contributor* should ignore, which
makes the project copy the one that travels and the global entry the redundant half. Deleting the
project line would leave anyone cloning without this machine's global file able to stage a real
`.env`, which is the opposite of the point.

### Shapes that stop the work rather than being fixed

- **A line carrying a backslash**, in either pass. Gitignore gives it a meaning this migration does
  not implement: a trailing space survives in `foo\ ` where `.strip()` would eat it, and `\#file` is
  a pattern rather than a comment. The stripped copy compared against the global file is then not
  the text anyone wrote. Print the line verbatim with its number, write nothing, and leave any
  duplicate beside it in place rather than deleting it on a reading that may be wrong.
- **A rule excluding a parent directory**, in pass 1. Git will not re-include a path whose parent is
  excluded, so a repo hiding `.claude/` wholesale cannot be repaired by adding `!.claude/memos/`
  below it — the negation is read and has no effect, which is worse than an error, because the file
  looks fixed. The entry has to become `.claude/*` with an explicit `!` re-include per committed
  path, and that changes what every other file under `.claude/` does. Name the excluded directory
  and stop.
- **A deletion that would expose something**, in pass 2. Before the lines go, record every path on
  disk each one is currently the winning rule for; afterwards assert each of those paths still
  ignored, one at a time. A path that becomes visible means putting every file back as it was and
  stopping — a whole-directory rule can be silently hiding real siblings, and exposing them is a
  per-file decision.
- **Every rule hiding a required path lives outside this repository** — the global excludes file, or
  `.git/info/exclude`. There is nothing here to edit and the question goes to the user. Neither file
  is committed and neither is this version's to change: the first is one decision about every repo
  on the machine, the second is invisible to everyone else and lost on re-clone. Name each path and
  the file and line behind it.
- **Nothing answers `git config --global core.excludesfile`**, or the file it names cannot be read.
  The pass-2 comparison then has no other side, and a project `.gitignore` full of `.DS_Store` lines
  is indistinguishable from one that is correct. Say so, ask for the setting — on this setup it
  points at a file symlinked out of the dotfiles repo — and start again once it answers.

### What the rewrite loses, and how to compare it

A comment whose only rules were removed goes with them, and one of them in this fleet recorded that
`.claude/memory/` stays tracked — true, and after the deletion written down nowhere but git history.
Read those comment lines first, then read `git diff @{upstream} -- '*.gitignore'` and check that
nothing arriving from the other machine re-introduces a rule this pass removed.

### Afterwards

- Check whether the newly visible files should be staged now. This changes what git *can* see; it
  stages nothing, and a `.claude/settings.json` hidden for months may have drifted into holding
  something machine-specific that belongs in `settings.local.json` instead.
- Where a wider pattern gained a `!` re-include, read what else that pattern still covers. The
  re-include names one path; the rule it sits under was written for a reason.
- Decide the anchoring this version does not touch. A floating `data/` or `backup/` in a repo with a
  nested `web/` tree may be hiding more than its author meant, and `git check-ignore -v` over the
  paths in question answers it in one call.
- Move a line to the global excludes file when it is being deleted from every repo in the fleet and
  is not already there. That file is out of reach here and no version governs its contents, so a
  rule dropped everywhere ends up nowhere unless somebody puts it there.

## When it does not apply

Both halves answer clean, and each needs its own evidence:

- Git, handed every required path at once, names none of them. That is read off the tool rather than
  inferred from a file's absence: the repo may hold none of those files today and still be in the
  target shape, because the shape is a fact about the rules, not about what happens to exist. Twelve
  of the fifteen repos answered this way when this version was written.
- Both sides were read and nothing in this repo's committed `.gitignore` files duplicates the global
  set. Say how many project files were read and how many global entries they were compared against,
  so "nothing found" is distinguishable from "nothing looked at".

A repo owning no `.gitignore` at all satisfies the second on its own, and reaches the first by the
same reading as any other repo — the global file can still hide a required path, and that is a
finding rather than a no-op.

## Continuing rule

`gitignore-unhides-committed` — git, asked about every path that must stay committed, names none of
them as ignored. A rule in the global excludes file fails it too, even though no edit inside the
repo can remove one: the repo is genuinely not in the target shape, and the question belongs to a
human rather than to a check that quietly passes.

`gitignore-scope-global` — no line in any `.gitignore` this repo commits duplicates an entry in the
global excludes file, and no bare `scripts/` line exists. Both sides are re-read from disk on every
run, so a later change to the global file is measured rather than frozen into whatever was true on
the day the repo adopted this.
