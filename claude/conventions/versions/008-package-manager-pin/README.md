---
title: The npm version is pinned in package.json
rules: package-manager-pin
---

## What changed

Two machines running different npm versions rewrite the lockfile against each other. The diff
touches no real dependency and only metadata — `"peer": true` markers appearing and disappearing,
`devOptional` flipping to `dev`, optional packages pruned and restored — and it recurs on every
install until the manager is pinned. Corepack reads `packageManager` and shims the manager to
exactly that version, so the pin is what makes two checkouts agree.

The set of manifests is the one `claude/conventions/rules/_node.py` derives, shared with every other
rule that reads one: a generated `web/.next/package.json` and every manifest under `node_modules/`
are outside it, and a repo holding two real ones has to pin both.

**Where the version comes from.** From this repo, or from the user — never from the network and
never from a constant. Resolving a version at run time would write a different answer into every
repo it visited; a constant is the same guess with a longer shelf life.

When exactly one npm version is named anywhere in this repo, that value is copied. A repo running
one manifest at `npm@11.17.0` must not gain a second at some newer number: the two would install
against two lockfiles with two managers, which is the drift this convention exists to stop. The
fleet's own spread — printlab at 11.17.0 while bga-assistant, scheduler, tripit and what-is-next are
at 11.18.0 — is exactly what that rule protects.

When nothing in the repo names a version, stop and ask. An earlier draft carried the then-current
stable as a constant and wrote it, which measured as a *major* above every pin in the fleet and
above the npm this machine runs — so Corepack would have fetched npm 12 and the first install would
have rewritten the lockfile, introducing the exact churn the convention exists to end. Choosing a
first pin for a repo is a decision with a blast radius past that repo, and a version `npm view`
would answer is a question for the user, not a lookup.

## Migrating an existing repo

There is work here when a project `package.json` carries no `packageManager` field and exactly one
npm version is named elsewhere in the repo for it to copy.

Show the concrete number and where it came from — "copied from web/package.json" — and ask before
writing, so the value reaches the user on screen rather than as an abstract question.

Fetch first, and do not run this on a branch behind its upstream: the migration rewrites a committed
`package.json`, adding one key, and the other machine may have added the same key with a different
version. If the manifest still differs from `@{upstream}` afterwards, compare
`git show @{upstream}:<manifest>` against what is on disk and keep one version per repo.

Four states are a question for the user rather than work to do:

- **A manifest pins another manager.** A `yarn@` or `pnpm@` value is a deliberate choice about how
  that project installs, and this version neither reverses it nor writes an npm pin alongside.
- **A manifest carries a `packageManager` that will not parse** — a range rather than an exact
  version, a bare major, a value that is not a string. Somebody typed it for a reason and replacing
  it is a different decision from filling in a blank.
- **The repo names two different npm versions and a third manifest has none.** Which of them a new
  manifest should carry is a question the repo itself does not answer, so name both and write
  nothing. Settling on one version across the repo is what unblocks it; two that are deliberate,
  with the manifests genuinely installing apart, is an answer the user gives.
- **No manifest in the repo names any npm version.** There is nothing to copy, and this picks none.
  Resolve the current stable with `npm view npm version`, check it against what the other repos here
  pin rather than taking it on sight, and ask for the chosen value — added to one manifest, every
  other manifest then copies it.

Hiding matters twice here, because an ignored manifest is not only a place a pin could be written
but a place one could be *copied from*: a repo whose tracked manifest lacks a pin must not take its
version from a scratch clone. A git that will not answer which paths it hides stops the work — an
unanswered question is not an empty skip set.

Afterwards:

- Run `corepack enable npm` once on each machine that builds this project. Plain `corepack enable`
  shims yarn and pnpm only — npm is a deliberate exception — so without the explicit form the pin is
  silently ignored and `npm -v` keeps reporting the bundled version. On Windows that command needs
  an elevated shell when Node sits under Program Files.
- Check `npm -v` inside the project reports the pinned version. That is the only proof the shim
  took; the field being present proves the intent and not the effect.
- Check the pinned npm can run on the Node this project targets. npm 12 requires Node
  `^22.22.2 || ^24.15.0 || >=26.0.0`, so a project pinned to an earlier Node 24 patch needs an npm 11
  pin instead — the declared engines range and this field have to be compatible, and no rule
  compares them.
- Run `npm install` once and commit whatever the lockfile does. The first install under a different
  manager version is the last metadata churn this repo should see.

## When it does not apply

The tree holds no `package.json` a person maintains — none outside the generated directories, and
none that git does not hide. That is positive evidence read off a walk of the whole repo: there is
no Node project here whose manager could drift.

A repo where every manifest already carries a pin in the `npm@x.y.z` form is the other reason.

## Continuing rule

`package-manager-pin` — every project manifest carries `packageManager` matching `npm@` plus a
three-part version. It asserts the pinned form and never a particular version: the spread across
this fleet is not a shape violation, and encoding today's number would fail every adopted repo the
day the next npm ships.
