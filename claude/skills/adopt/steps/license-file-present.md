---
version: 10
slug: license-file-present
title: A LICENSE file sits at the repo root
scope: repo
---

# A LICENSE file sits at the repo root

A repo carrying no LICENSE grants nothing to anyone who obtains a copy. That is the same
position as all rights reserved, reached by accident rather than on purpose, and it reads to
anyone who opens the repo as an oversight instead of a decision. The convention is that the
position is written down: a `LICENSE` at the repo root, with the current year and the holder's
name, MIT for a public repo and all rights reserved for a private one.

Three repos in the fleet carry GPL-3 instead, deliberately. So this step asserts that a license
is **present** and never what it says — an `applied` line here means the decision was written
down, not that it was the right one.

Three repos had none when this step was written, which is what motivated it: **travel-map**,
public and carries no LICENSE at all, and **printlab** and **scheduler**, both private, where
the default the conventions name is all rights reserved rather than MIT. The `github-create`
skill seeds the file in its root commit, so every repo created through it already holds one;
these three predate that.

**This step detects and never fixes.** It has a `verify` and a `probe`, and its `apply` stops
with the finding and the two candidate texts instead of writing a file. Three reasons, and any
one of them is enough:

- The choice is legally the user's. A file the repo's owner did not choose is a grant nobody
  made, and once it is in a commit it has been offered on those terms to everyone holding a
  copy.
- The default flips on visibility, and visibility is a network fact. The command that answers it
  is `gh repo view --json isPrivate`, which no step script may run.
- Three repos already deviate from the default on purpose. A script writing MIT over a
  considered GPL-3 decision would be guessing at exactly the place where guessing costs the
  most, and a wrong LICENSE is not undone by deleting the file — old commits still carry it.

## Applies when

Never, as far as `probe` is concerned: it cannot return 0 in any repo, so `/adopt` never reaches
`apply` here.

The convention itself applies to every repo in the fleet — each is a real project that wants its
terms written down. What no script can reach is the target shape, because the file's content is
a legal choice rather than a transformation of something already on disk. So the work is split:
`verify` hands a free `applied` line to every repo that already holds a license, and the rest
reach the question below.

## Does not apply when

Never, and that is a deliberate refusal rather than an oversight.

Exit 1 needs positive evidence that a repo wants no license decision, and no file on disk
carries that evidence. An absent LICENSE is the finding itself, not proof there is nothing to
find. A `package.json` declaring `"private": true` comes closest and still says only that the
package is not published to a registry, which is a different question from what a person holding
a copy of the source may do with it.

A repo whose owner is content with the implicit default records `declined`, through the question
below. That is an answer a human gave, not one a probe inferred.

## Cannot tell

Always, and `probe` says so with the repo's own state in front of it. Four states reach the same
question by different routes:

- **No LICENSE, LICENSE.md, LICENSE.txt or COPYING at the repo root** — the finding, and the
  state all three named repos are in.
- **One of those is present but holds nothing** — an empty file grants nothing and says nothing,
  so it is the absent case wearing a filename.
- **One of those is present as a directory** — a name that reads as a license from a file
  listing and is not one.
- **A license is already present** — then `verify` has answered this repo without a question,
  and what is left is whether that license is the one its visibility calls for. That half is a
  human's, and it is under *By hand* below rather than in any exit code.

The question, as the user reads it: this repo's license position is not written down. Is the
repo public or private? `gh repo view --json isPrivate` answers it, and the conventions default
public to MIT and private to all rights reserved. Run `apply` for this step to see both
candidate texts in full, with the year and holder already filled in; write the chosen one to
`LICENSE` at the repo root and re-run, which records `applied`. Record `n/a` if this directory
is not a project whose terms matter — a scratch tree, a vendored copy — and `declined` if the
absence is deliberate and the implicit all-rights-reserved default is the position wanted.

## Verify

The target shape is one non-empty file named `LICENSE`, `LICENSE.md`, `LICENSE.txt` or `COPYING`
at the repo root, matched on a case-folded name so a repo spelling it in lower case reads the
same on a case-sensitive filesystem as it does here.

It is not vacuous in two ways that matter. An empty directory fails it, which is what proves the
check can tell a repo in the shape from one that never got there. And a file that exists while
holding nothing fails it too, because a zero-byte LICENSE passes every presence check ever
written and grants exactly as much as no file at all.

Presence is the whole assertion. Whether the license is MIT, GPL-3 or a reservation, and whether
that matches the repo's visibility, is deliberately not checked — three repos deviate from the
default on purpose, so a content check would report the fleet's considered decisions as
failures. The recorded note therefore claims only what was looked at.

Exit 2 is kept for the one thing that is genuinely unobservable: a repo root that cannot be
listed, or a candidate file that cannot be read, so whether it holds anything is unknown. A
license that is plainly there and plainly empty is exit 3, not exit 2 — the shape was observed,
and it is the wrong one.

## By hand, after the script

- Answer the visibility question before choosing: `gh repo view --json isPrivate` for this
  repo's slug. Public defaults to MIT, private to all rights reserved.
- Read `learnings/software-licensing-choices.md` before departing from either default. It has
  the decision table, what AGPL does and does not stop, and the source-available options.
- Check the private-plus-MIT pairing twice. MIT grants rights to whoever obtains a copy, so it
  takes effect the moment a private repo is shared or opened — and it does that from the commit
  that introduced it, which is the hardest one in the history to take back.
- Update the package manifest as well, where one exists. A manifest still naming a different
  license contradicts the file and is what dependency scanners actually read; npm's documented
  spelling for no grant is `"license": "UNLICENSED"`, paired with `"private": true`, and
  `npm install --package-lock-only` refreshes the lockfile's root entry to match.
- Confirm sole authorship before treating the file as freely changeable:
  `git log --format='%an <%ae>' | sort -u`, plus a grep for `Co-authored-by` and `Signed-off-by`
  trailers. One outside commit with no CLA and relicensing is no longer the owner's alone.
- Where a license is replaced rather than added, keep the previous terms under a dated note.
  Copies already taken stay under the terms they were offered on, and the note is what settles
  later which terms applied when.
