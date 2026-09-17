---
title: Project .gitignore drops global-file lines
rules: gitignore-scope-global
---

## What changed

An ignore rule for a user-specific artifact — an IDE folder, an OS cache, a per-machine wrapper a
personal skill writes — belongs in the global excludes file, where one line covers every repo. A
copy of the same line inside a project `.gitignore` buys nothing and costs twice: it puts a
machine-local detail in a file every contributor reads, and it is a second copy that drifts, so a
repo keeping its own `config/deploy.env` line goes on enforcing a rule the global file may have
moved past.

The global file is located through `git config --global core.excludesfile`, never assumed to be
`~/.gitignore`. That lookup is doing real work: this machine's setting is the literal string
`~/.gitignore`, which no `open()` resolves, so anything that hard-coded the path *and* skipped
`expanduser` would happen to work here and fail the moment either changed.

Two kinds of line go, and nothing else does.

- **A duplicate** — the same entry, after stripping a leading `**/`, appears in the global file, and
  either the `.gitignore` sits at the repo root or the pattern floats.
- **A bare `scripts/` line** — it supersedes the global file's root-anchored wrapper entries with a
  pattern that matches at any depth, and hides the repo's own committed scripts as well. One repo
  tracks `scripts/package.ts` under exactly such a line.

**Anchoring is out of scope, deliberately.** CLAUDE.md asks a project pattern to carry a leading
slash "unless matching at any depth is intended", and that clause makes the question undecidable
from the file alone: the fleet holds eleven floating patterns — `data/`, `backup/`, `cities/`,
`.wrangler/` and the rest — each of which is plausibly written that way on purpose. Asserting
anchoring would report all eleven and be right about none of them, which is noise rather than a
finding. What this version deletes is decided by comparing two files, so it never has to guess an
intention.

## Migrating an existing repo

There is work here when a `.gitignore` this repo commits holds at least one duplicate line, or a
bare `scripts/` line.

Read which files count from `git ls-files`, not from a directory walk. A virtualenv, a build
directory and an IDE each write a `.gitignore` of their own — the fleet holds nine, under `.venv/`,
`.next/` and `.idea/` — and rewriting one of those would be editing something the repo neither owns
nor keeps.

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

Fetch first, and do not run this on a branch behind its upstream: the migration deletes lines from a
committed file, and a deletion here merges cleanly against an addition made on the other machine,
losing it without a conflict.

Two shapes stop the work rather than being fixed:

- **A line carrying a backslash.** Gitignore gives it a meaning this migration does not implement —
  a trailing space survives in `foo\ ` where `.strip()` would eat it, and `\#file` is a pattern
  rather than a comment. The stripped copy compared against the global file is then not the text
  anyone wrote, so print the line verbatim with its number, write nothing, and leave any duplicate
  beside it in place rather than deleting it on a reading that may be wrong.
- **A deletion that would expose something.** Before the lines go, record every path on disk each
  one is currently the winning rule for; afterwards assert each of those paths still ignored, one at
  a time. A path that becomes visible means putting every file back as it was and stopping — a
  whole-directory rule can be silently hiding real siblings, and exposing them is a per-file
  decision.

Nothing answering `git config --global core.excludesfile`, or a file it names that cannot be read,
is a question rather than a finding. The comparison then has no other side, and a project
`.gitignore` full of `.DS_Store` lines is indistinguishable from one that is correct. Say so, ask
for the setting — on this setup it points at a file symlinked out of the dotfiles repo — and start
again once it answers.

What the deletion loses, and how to compare it: a comment whose only rules were removed goes with
them, and one of them in this fleet recorded that `.claude/memory/` stays tracked — true, and after
the deletion written down nowhere but git history. Read those comment lines before removing them,
then read `git diff @{upstream} -- '*.gitignore'` and check that nothing arriving from the other
machine re-introduces a line this pass removed.

Afterwards:

- Check whether anything the deleted lines were hiding should now be committed. The assertion above
  is that each such path is still ignored *by the global file*; it does not ask whether being
  ignored was right, and a whole-directory rule is the usual place a real file has been sitting
  unseen.
- Decide the anchoring this version does not touch. A floating `data/` or `backup/` in a repo with a
  nested `web/` tree may be hiding more than its author meant, and `git check-ignore -v` over the
  paths in question answers it in one call.
- Move a line to the global excludes file when it is being deleted from every repo in the fleet and
  is not already there. That file is out of reach here and no version governs its contents, so a
  rule dropped everywhere ends up nowhere unless somebody puts it there.

## When it does not apply

Both sides were read and nothing in this repo's committed `.gitignore` files duplicates the global
set, or the repo commits no `.gitignore` at all. That is evidence from having opened both files
rather than from an absence: say how many project files were read and how many global entries they
were compared against, so "nothing found" is distinguishable from "nothing looked at".

## Continuing rule

`gitignore-scope-global` — no line in any `.gitignore` this repo commits duplicates an entry in the
global excludes file, and no bare `scripts/` line exists. Both sides are re-read from disk on every
run, so a later change to the global file is measured rather than frozen into whatever was true on
the day the repo adopted this.
