---
title: Project .gitignore stops hiding committed files
rules: gitignore-unhides-committed
---

## What changed

Several paths in this system are meant to travel with the repo: `.claude/settings.json`,
`.claude/memory/`, `.claude/memos/`, `.claude/conventions` and `config/publish.env`. A project
`.gitignore` rule covering any of them makes that file silently never stage. Nothing reports it —
`git add` is quiet, `git status` shows no untracked entry — and the loss surfaces on the other
machine as a file that was never there. The `config/publish.env` case is the one already paid for:
keeping it ignored meant each machine held its own hand-edited copy, and those copies drifted until
one named a compose service that had not existed for six days.

This version comes before every later one that writes into `.claude/`, because a record written
into a hidden directory is a record nobody can commit.

## Migrating an existing repo

There is work here when a rule in a `.gitignore` this repo commits makes git hide at least one of
those paths.

Put the question to `git check-ignore` rather than answering it by reading the file, so a pattern
reaching a path by a route nobody predicted — `**/config/*.env` over `config/publish.env` — is
caught as readily as one naming it outright. Two flags decide what the answer means:

- The plain form of the command is what says "ignored". The `-v` form exits 0 on a *negation* as
  well, because its status answers "did any pattern apply" and a `!` rule applies as much as an
  exclusion does. Reading that status as a verdict gets the answer backwards on exactly the paths a
  negation exists to protect. Use `-v` to find the file and line behind a hit, never to decide
  whether there was one.
- Pass `--no-index` on every call. By default the command consults the index and calls a *tracked*
  path not ignored whatever the rules say, so a repo that once force-added a file it excludes would
  answer "no deviation" while the rule still hides every new file beside it.

Fetch first, and do not run this on a branch behind its upstream: the migration rewrites a committed
file the other machine may have edited, and a line deleted here merges cleanly against a line added
there. Then delete the offending rule from the committed `.gitignore`, or re-include the path below
it where the rest of the pattern is still wanted.

Two shapes stop the work rather than being fixed:

- **A rule excluding a parent directory.** Git will not re-include a path whose parent is excluded,
  so a repo hiding `.claude/` wholesale cannot be repaired by adding `!.claude/memos/` below it —
  the negation is read and has no effect, which is worse than an error, because the file looks
  fixed. The entry has to become `.claude/*` with an explicit `!` re-include per path that stays
  committed, and that changes what every other file under `.claude/` does. Name the excluded
  directory and stop.
- **A line carrying a backslash.** Gitignore gives the backslash a meaning this migration does not
  implement: `foo\ ` keeps a trailing space, and `\#file` is a pattern rather than a comment.
  Rewriting a file holding one means rewriting text nobody matched, so print the line verbatim with
  its number and write nothing.

Where every rule hiding a required path lives outside this repository — the global excludes file,
or `.git/info/exclude` — there is nothing here to edit, and the question goes to the user. Neither
file is committed and neither is this version's to change: the first is one decision about every
repo on the machine, the second is invisible to everyone else and lost on re-clone. Name each path
and the file and line behind it; the answer is either to remove the rule there or to re-include the
path in this repo's `.gitignore` by hand.

What the rewrite loses, and how to compare it: a comment whose only rule was removed goes with it,
so read those words before the deletion and check the diff for anything real among them, since
afterwards they exist only in git history. If `.gitignore` still differs from `@{upstream}`, read
`git diff @{upstream} -- .gitignore` and check that nothing arriving from the other machine
re-introduces a rule over one of these paths.

Afterwards:

- Check whether the newly visible files should be staged now. This changes what git *can* see; it
  stages nothing, and a `.claude/settings.json` that has been hidden for months may have drifted
  into holding something machine-specific that belongs in `settings.local.json` instead.
- Where a wider pattern gained a `!` re-include, read what else that pattern still covers. The
  re-include names one path; the rule it sits under was written for a reason, and the other files
  it hides are meant to stay hidden.

## When it does not apply

Git, handed every one of those paths at once, names none of them. That is evidence read off the
tool itself rather than inferred from a file's absence: the repo may hold none of those files today
and still be in the target shape, because the shape is a fact about the rules, not about what
happens to exist. Twelve of the fifteen repos answered this way when this version was written.

A repo owning no `.gitignore` at all is the same answer by the same reading.

## Continuing rule

`gitignore-unhides-committed` — git, asked about every path that must stay committed, names none of
them as ignored. A rule in the global excludes file fails it too, even though no edit inside the
repo can remove one: the repo is genuinely not in the target shape, and the question belongs to a
human rather than to a check that quietly passes.
