---
version: 7
slug: node-engines-declared
title: The Node engines range is declared
scope: repo
---

# The Node engines range is declared

A project says which Node it targets in two places and they do different jobs. The `.nvmrc`
tells a developer's shell what to install; `engines.node` in `package.json` tells npm, CI, a
container build and every tool that reads a manifest. A project carrying only the first builds
on whatever runtime the machine happened to have, and v8 is what turns the second from advice
into a hard error — so this step comes first, and a repo walked in the other order would record
that it has no range a minute before it gains one.

Nothing here invents a version. The range is derived from the `.nvmrc` sitting beside the
manifest, and a manifest with no `.nvmrc` beside it is a question: "24" and a deliberate older
pin read identically from a file that does not exist.

## Which package.json counts

A repo whose app lives under `web/` also carries `web/.next/package.json`, sometimes
`web/.next/standalone/package.json`, and one manifest per installed dependency under
`node_modules/`. A plain `find` returns all of them. This step walks the tree and never
descends into a directory a build tool or a package manager owns — the list is in
`node_manifests.py`, which v8 and v9 read too, so the three cannot disagree about which files
they are talking about.

Every manifest that survives that walk is a project's, and each is asserted on its own. A repo
holding two of them — an app and a helper with its own lockfile — must satisfy the convention
in both, or say why not.

## Applies when

A project `package.json` declares no `engines.node`, and an `.nvmrc` beside it names a version
the major can be read from. The range written is `>=<major> <<major+1>`, which is the form the
rest of the fleet already uses.

## Does not apply when

The tree holds no `package.json` a person maintains — none outside the generated directories
above, and none that git does not hide. That is positive evidence read off a walk of the whole
repo rather than off one path's absence: there is no Node project here, so there is no range to
declare. A manifest git hides is nobody's to edit, and the global convention puts scratch in a
gitignored `tmp/`, so a clone sitting in one is a designed condition rather than an accident.
A git that will not answer which paths it hides is a third outcome and not an empty skip set:
the step prints what it could not establish and exits 3 without writing.

Every manifest already declaring `engines.node`, with an `.nvmrc` beside it that the range
admits, is the other reason. Verify sees that first and records the repo as in the target shape
without touching anything; probe repeats the same reading for anyone who runs it directly.

## Cannot tell

- **A manifest declares no range and has no readable `.nvmrc` beside it.** Which Node this
  project targets is written nowhere in the repo, and the current LTS is a default for a new
  project rather than a claim about an existing one. Add the `.nvmrc` and re-run, or record
  `n/a` when the project deliberately targets no particular runtime.
- **A manifest declares a range and has no `.nvmrc` beside it.** The declaration is there and
  the thing a developer's shell reads is not. Which version belongs in that file is not
  derivable from a range — `>=24` admits every 24.x — so it is a human's to write.
- **The two disagree.** An `.nvmrc` naming a version the declared range excludes is a real
  contradiction and either side could be the wrong one. A partial `.nvmrc` such as `24` is read
  as 24.0.0, the lowest runtime that pin permits, because a range the lowest permitted version
  fails is a range the pin does not guarantee.
- **The range is written in a form this step cannot read.** Hyphen ranges, prerelease tags and
  `lts/*` are all real things to write and none of them is a comparator set this step parses.
  It reports the range unread rather than assuming it agrees, because an unasserted line must
  never read as a passed one.

A repo where one manifest is derivable and another is blocked goes to the question as a whole.
Applying to the derivable half would leave verify failing straight afterwards, which stops the
`/adopt` run anyway, with half the change already written.

## Fetch before running

This step rewrites a committed `package.json`, adding one key. The `/adopt` procedure refuses
to start on a branch behind its upstream, which is the gate that matters: the other machine may
have added the same key with a different range, and two adds merge into a conflict rather than
into a loss. If the manifest still differs from `@{upstream}` afterwards, compare
`git show @{upstream}:<manifest>` against what is on disk and keep whichever range the `.nvmrc`
actually admits.

## Verify

Every project manifest declares `engines.node`, an `.nvmrc` sits beside it, and the version that
`.nvmrc` names falls inside the declared range. All three are re-derived from disk.

It asserts agreement between the two files and never a particular major. A check for "is it 24"
would fail the whole fleet the day the LTS line moves and would keep failing in every `audit`
run after that — a permanent false alarm is how a real finding stops being read.

It cannot pass vacuously. A repo holding no manifest at all is exit 2 with that as the reason
rather than exit 0: "every manifest declares a range" is true of a repo holding none, and an
`applied` line there would claim work in a repo the convention never reaches. Probe answers that
case with positive evidence and the line is recorded `n/a`.

A range this step cannot read is exit 2 as well, since neither agreement nor disagreement was
established. A manifest that is not valid JSON is exit 3 — that is not an unobservable shape,
it is a broken file.

## By hand, after the script

- Check what actually installs Node for this project — a Dockerfile's base image, a CI
  workflow's `setup-node`, a hosting platform's runtime setting. This step asserts the two files
  in the repo agree with each other; nothing in a manifest can say what a build image ships, and
  a `node:22-alpine` under a `>=24` range fails at run time rather than at install time.
- Read the range it wrote. `>=24 <25` is the fleet's shape and pins the major deliberately; a
  project that genuinely wants the next major as soon as it ships wants `>=24` instead, and that
  is an edit, not a defect.
- Where the step asked about a missing `.nvmrc`, write the version rather than the major when
  the project is sensitive to a patch level — one dependency in this fleet compiles differently
  against Node 24.19 headers than against 24.15, and only the full version records which side of
  that the project is on.
