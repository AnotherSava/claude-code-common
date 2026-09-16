---
title: A LICENSE file sits at the repo root
scope: repo
---

## What changed

A repo carrying no LICENSE grants nothing to anyone who obtains a copy. That is the same position as
all rights reserved, reached by accident rather than on purpose, and it reads to anyone who opens the
repo as an oversight instead of a decision. The convention is that the position is written down: a
`LICENSE` at the repo root, with the current year and the holder's name, MIT for a public repo and
all rights reserved for a private one.

Three repos in the fleet carry GPL-3 instead, deliberately. So what is asserted is that a license is
**present** and never what it says — adopting this means the decision was written down, not that it
was the right one.

Three repos had none when this version was written, which is what motivated it: **travel-map**,
public and carrying no LICENSE at all, and **printlab** and **scheduler**, both private, where the
default the conventions name is all rights reserved rather than MIT. The `github-create` skill seeds
the file in its root commit, so every repo created through it already holds one; these three predate
that.

**This one asks and never writes on its own.** Three reasons, and any one of them is enough:

- The choice is legally the user's. A file the repo's owner did not choose is a grant nobody made,
  and once it is in a commit it has been offered on those terms to everyone holding a copy.
- The default flips on visibility, and visibility is a network fact. The command that answers it is
  `gh repo view --json isPrivate`.
- Three repos already deviate from the default on purpose. Writing MIT over a considered GPL-3
  decision would be guessing at exactly the place where guessing costs the most, and a wrong LICENSE
  is not undone by deleting the file — old commits still carry it.

## Migrating an existing repo

There is a question here in every repo that does not already hold a license, and it is the user's to
answer. Four states reach it by different routes:

- **No LICENSE, LICENSE.md, LICENSE.txt or COPYING at the repo root** — the finding, and the state
  all three named repos are in.
- **One of those is present but holds nothing** — an empty file grants nothing and says nothing, so
  it is the absent case wearing a filename.
- **One of those is present as a directory** — a name that reads as a license from a file listing
  and is not one.
- **A license is already present** — then there is nothing to migrate, and what is left is whether
  that license is the one its visibility calls for. That half is a human's, and it is under
  *Afterwards* below.

The question, as the user reads it: this repo's license position is not written down. Is the repo
public or private? `gh repo view --json isPrivate` answers it, and the conventions default public to
MIT and private to all rights reserved. Show both candidate texts in full, with the year taken from
the clock and the holder's name from `git config user.name`, and write the chosen one to `LICENSE`
at the repo root. An owner content with the implicit all-rights-reserved default is an answer too,
and writes no file — either way the position has been decided rather than left unexamined, which is
the whole of what this version asks for.

A repo root that cannot be listed, or a candidate file that cannot be read, stops the work rather
than becoming the finding: whether it holds anything is unknown, and an absent license is a
different fact from an unreadable one.

Afterwards:

- Read `learnings/software-licensing-choices.md` before departing from either default. It has the
  decision table, what AGPL does and does not stop, and the source-available options.
- Check the private-plus-MIT pairing twice. MIT grants rights to whoever obtains a copy, so it takes
  effect the moment a private repo is shared or opened — and it does that from the commit that
  introduced it, which is the hardest one in the history to take back.
- Update the package manifest as well, where one exists. A manifest still naming a different license
  contradicts the file and is what dependency scanners actually read; npm's documented spelling for
  no grant is `"license": "UNLICENSED"`, paired with `"private": true`, and
  `npm install --package-lock-only` refreshes the lockfile's root entry to match.
- Confirm sole authorship before treating the file as freely changeable:
  `git log --format='%an <%ae>' | sort -u`, plus a grep for `Co-authored-by` and `Signed-off-by`
  trailers. One outside commit with no CLA and relicensing is no longer the owner's alone.
- Where a license is replaced rather than added, keep the previous terms under a dated note. Copies
  already taken stay under the terms they were offered on, and the note is what settles later which
  terms applied when.

## When it does not apply

Never, and that is a deliberate refusal rather than an oversight. Skipping needs positive evidence
that a repo wants no license decision, and no file on disk carries that evidence. An absent LICENSE
is the finding itself, not proof there is nothing to find. A `package.json` declaring
`"private": true` comes closest and still says only that the package is not published to a registry,
which is a different question from what a person holding a copy of the source may do with it.

A directory that is not a project whose terms matter — a scratch tree, a vendored copy — is not
something this reasons about either: a third-party clone adopts nothing at all.

The one state with nothing to do is a repo already holding a non-empty `LICENSE`, `LICENSE.md`,
`LICENSE.txt` or `COPYING` at the root, matched on a case-folded name so a repo spelling it in lower
case reads the same on a case-sensitive filesystem as it does here.

## Continuing rule

None — this is a one-time migration.
