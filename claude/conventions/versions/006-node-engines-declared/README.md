---
title: The Node engines range is declared
rules: node-engines
---

## What changed

A project says which Node it targets in two places and they do different jobs. The `.nvmrc` tells a
developer's shell what to install; `engines.node` in `package.json` tells npm, CI, a container build
and every tool that reads a manifest. A project carrying only the first builds on whatever runtime
the machine happened to have, and the version after this one is what turns the second from advice
into a hard error — so this comes first, and a repo walked in the other order would record that it
has no range a minute before it gains one.

Nothing here invents a version. The range is derived from the `.nvmrc` sitting beside the manifest,
and a manifest with no `.nvmrc` beside it is a question: "24" and a deliberate older pin read
identically from a file that does not exist.

**Which package.json counts.** A repo whose app lives under `web/` also carries
`web/.next/package.json`, sometimes `web/.next/standalone/package.json`, and one manifest per
installed dependency under `node_modules/`. A plain `find` returns all of them. The set that counts
is the one `claude/conventions/rules/_node.py` derives: a walk that never descends into a directory
a build tool or a package manager owns, minus the paths git hides, so every rule that reads a
manifest agrees about which files they are talking about. Ask git what it hides through
`_git.ignored_untracked`, the index-consulting form, so a force-added file inside an ignored
directory still counts.

Every manifest that survives that walk is a project's, and each is asserted on its own. A repo
holding two of them — an app and a helper with its own lockfile — must satisfy the convention in
both, or say why not.

## Migrating an existing repo

There is work here when a project `package.json` declares no `engines.node` and an `.nvmrc` beside
it names a version whose major can be read. Write `>=<major> <<major+1>`, which is the form the rest
of the fleet already uses.

Fetch first, and do not run this on a branch behind its upstream: the migration rewrites a committed
`package.json`, adding one key, and the other machine may have added the same key with a different
range. If the manifest still differs from `@{upstream}` afterwards, compare
`git show @{upstream}:<manifest>` against what is on disk and keep whichever range the `.nvmrc`
actually admits.

Four states are a question for the user rather than work to do:

- **A manifest declares no range and has no readable `.nvmrc` beside it.** Which Node this project
  targets is written nowhere in the repo, and the current LTS is a default for a new project rather
  than a claim about an existing one. Ask for the `.nvmrc`, or for a statement that the project
  deliberately targets no particular runtime.
- **A manifest declares a range and has no `.nvmrc` beside it.** The declaration is there and the
  thing a developer's shell reads is not. Which version belongs in that file is not derivable from a
  range — `>=24` admits every 24.x — so it is a human's to write.
- **The two disagree.** An `.nvmrc` naming a version the declared range excludes is a real
  contradiction and either side could be the wrong one. Read a partial `.nvmrc` such as `24` as
  24.0.0, the lowest runtime that pin permits, because a range the lowest permitted version fails is
  a range the pin does not guarantee.
- **The range is written in a form that will not parse.** Hyphen ranges, prerelease tags and `lts/*`
  are all real things to write and none of them is a comparator set. Report the range unread rather
  than assuming it agrees, because an unasserted line must never read as a passed one.

A repo where one manifest is derivable and another is blocked goes to the question as a whole.
Writing the derivable half would leave the continuing rule failing straight afterwards, with half
the change already made.

A manifest that is not valid JSON stops the work rather than becoming a question — that is a broken
file, not an unobservable shape. A git that will not answer which paths it hides stops it too: an
unanswered question is not an empty skip set.

Afterwards:

- Check what actually installs Node for this project — a Dockerfile's base image, a CI workflow's
  `setup-node`, a hosting platform's runtime setting. The two files in the repo agreeing with each
  other is the whole of what is asserted; nothing in a manifest can say what a build image ships,
  and a `node:22-alpine` under a `>=24` range fails at run time rather than at install time.
- Read the range that was written. `>=24 <25` is the fleet's shape and pins the major deliberately;
  a project that genuinely wants the next major as soon as it ships wants `>=24` instead, and that
  is an edit, not a defect.
- Where the question above was about a missing `.nvmrc`, write the version rather than the major
  when the project is sensitive to a patch level — one dependency in this fleet compiles
  differently against Node 24.19 headers than against 24.15, and only the full version records
  which side of that the project is on.

## When it does not apply

The tree holds no `package.json` a person maintains — none outside the generated directories above,
and none that git does not hide. That is positive evidence read off a walk of the whole repo rather
than off one path's absence: there is no Node project here, so there is no range to declare. A
manifest git hides is nobody's to edit, and the global convention puts scratch in a gitignored
`tmp/`, so a clone sitting in one is a designed condition rather than an accident.

Every manifest already declaring `engines.node`, with an `.nvmrc` beside it that the range admits,
is the other reason.

## Continuing rule

`node-engines` — every project manifest declares `engines.node`, an `.nvmrc` sits beside it, and the
version that `.nvmrc` names falls inside the declared range. It asserts agreement between the two
files and never a particular major: a check for "is it 24" would fail the whole fleet the day the
LTS line moves, and a permanent false alarm is how a real finding stops being read.
