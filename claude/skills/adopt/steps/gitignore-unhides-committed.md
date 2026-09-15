---
version: 2
slug: gitignore-unhides-committed
title: Project .gitignore stops hiding committed files
scope: repo
script: gitignore-unhides-committed.py
---

# Project .gitignore stops hiding committed files

Five paths in this system are meant to travel with the repo: `.claude/settings.json`,
`.claude/memory/`, `.claude/memos/`, `.claude/conventions.tsv` and `config/publish.env`. A
project `.gitignore` rule covering any of them makes that file silently never stage. Nothing
reports it — `git add` is quiet, `git status` shows no untracked entry — and the loss surfaces
on the other machine as a file that was never there. The `config/publish.env` case is the one
already paid for: keeping it ignored meant each machine held its own hand-edited copy, and those
copies drifted until one named a compose service that had not existed for six days.

This step goes before every later one that writes into `.claude/`, because a record written into
a hidden directory is a record nobody can commit.

## Applies when

A rule in a `.gitignore` this repo commits makes git hide at least one of those five paths.

The question is put to `git check-ignore` rather than answered by reading the file, so a pattern
reaching a path by a route nobody predicted — `**/config/*.env` over `config/publish.env` — is
caught as readily as one naming it outright.

Two flags decide what the answer means. The plain form of the command is what says "ignored":
the `-v` form exits 0 on a *negation* as well, because its status answers "did any pattern
apply" and a `!` rule applies as much as an exclusion does. Reading that status as a verdict
gets the answer backwards on exactly the paths a negation exists to protect. And every call
passes `--no-index`, because by default the command consults the index and calls a *tracked*
path not ignored whatever the rules say — a repo that once force-added a file it excludes would
answer "no deviation" while the rule still hides every new file beside it.

## Does not apply when

Git, handed all five paths at once, names none of them. That is evidence read off the tool
itself rather than inferred from a file's absence: the repo may hold none of those files today
and still be in the target shape, because the shape is a fact about the rules, not about what
happens to exist. Twelve of the fifteen repos answered this way when this step was written.

## Cannot tell

Every rule hiding a required path lives outside this repository — the global excludes file, or
`.git/info/exclude`. Neither is committed and neither is this step's to edit: the first is one
decision about every repo on the machine, the second is invisible to everyone else and lost on
re-clone. The printed question names each path and the file and line behind it, and the answer
is either to remove the rule there or to re-include the path in this repo's `.gitignore` by
hand. Record `declined` when the rule stays where it is deliberately, and re-run after removing
it otherwise, which records `applied`.

Two shapes stop `apply` rather than probe:

- **A rule excluding a parent directory.** Git will not re-include a path whose parent is
  excluded, so a repo hiding `.claude/` wholesale cannot be repaired by adding `!.claude/memos/`
  below it — the negation is read and has no effect, which is worse than an error, because the
  file looks fixed. The entry has to become `.claude/*` with an explicit `!` re-include per path
  that stays committed, and that changes what every other file under `.claude/` does. The run
  names the excluded directory and stops.
- **A line carrying a backslash.** Gitignore gives the backslash a meaning this step does not
  implement: `foo\ ` keeps a trailing space, and `\#file` is a pattern rather than a comment.
  Rewriting a file holding one means rewriting text nobody matched, so the line is printed
  verbatim with its number and nothing is written.

## Fetch before running

This step rewrites a committed file the other machine may have edited, and a line deleted here
merges cleanly against a line added there. The `/adopt` procedure refuses to start on a branch
behind its upstream, which is the gate that matters.

Afterwards, if `.gitignore` still differs from `@{upstream}`, read
`git diff @{upstream} -- .gitignore` and check that nothing arriving from the other machine
re-introduces a rule over one of the five paths.

## Verify

Git is handed all five required paths on one call and names none of them as ignored.

Asserted against the tool rather than against the text of any `.gitignore`, which is what makes
it survive a pattern nobody anticipated. It cannot pass vacuously: the assertion is the output
of a command that only runs inside a work tree, so an empty directory cannot answer 0 — it
answers "not observable" and the step says so. A repo owning no `.gitignore` at all passes, and
correctly: the target shape is that nothing hides these paths, never that a file was edited.

A rule in the global excludes file fails this too, even though `apply` cannot fix it. That is
deliberate — the repo is genuinely not in the target shape, and `probe` then puts the question
to a human rather than the record claiming a pass nobody made.

## By hand, after the script

- Read the lines the run reported as carried out with a deletion. A comment whose only rule was
  removed goes with it, and anything real among those words now exists only in git history.
- Check whether the newly visible files should be staged now. This step changes what git *can*
  see; it stages nothing, and a `.claude/settings.json` that has been hidden for months may have
  drifted into holding something machine-specific that belongs in `settings.local.json` instead.
- Where a wider pattern gained a `!` re-include, read what else that pattern still covers. The
  re-include names one path; the rule it sits under was written for a reason, and the other
  files it hides are meant to stay hidden.
