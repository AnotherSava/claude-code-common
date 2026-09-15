---
version: 9
slug: package-manager-pin
title: The npm version is pinned in package.json
scope: repo
---

# The npm version is pinned in package.json

Two machines running different npm versions rewrite the lockfile against each other. The diff
touches no real dependency and only metadata — `"peer": true` markers appearing and
disappearing, `devOptional` flipping to `dev`, optional packages pruned and restored — and it
recurs on every install until the manager is pinned. Corepack reads `packageManager` and shims
the manager to exactly that version, so the pin is what makes two checkouts agree.

The set of manifests is the one `node_manifests.py` derives, shared with v7 and v8: a generated
`web/.next/package.json` and every manifest under `node_modules/` are outside it, and a repo
holding two real ones has to pin both.

## Where the version comes from

From this repo, or from the user — never from the network and never from a constant. A step that
resolved a version at run time would write a different answer into every repo it visited, and
idempotence rule 4 rules it out; a constant compiled into the step is the same guess with a
longer shelf life.

When exactly one npm version is named anywhere in this repo, that value is copied. A repo running
one manifest at `npm@11.17.0` must not gain a second at some newer number: the two would install
against two lockfiles with two managers, which is the drift this convention exists to stop. The
fleet's own spread — printlab at 11.17.0 while bga-assistant, scheduler, tripit and what-is-next
are at 11.18.0 — is exactly what that rule protects.

When nothing in the repo names a version, the step stops and asks. An earlier draft carried the
then-current stable as a constant and wrote it, which measured as a *major* above every pin in
the fleet and above the npm this machine runs — so Corepack would have fetched npm 12 and the
first install would have rewritten the lockfile, introducing the exact churn the convention
exists to end. Choosing a first pin for a repo is a decision with a blast radius past that repo,
and `authoring-a-step.md` names this case outright: a version `npm view` would answer is a
question for the user, not a lookup.

## Applies when

A project `package.json` carries no `packageManager` field, and exactly one npm version is named
elsewhere in the repo for it to copy.

The `/adopt` walk shows `apply --dry-run` and asks before anything is written, and the dry run
prints the value together with where it came from — "copied from web/package.json". So the
concrete number reaches the user on screen rather than as an abstract question.

## Does not apply when

The tree holds no `package.json` at all outside the generated directories. That is positive
evidence read off a walk of the whole repo: there is no Node project here whose manager could
drift.

A repo where every manifest already carries a pin in the `npm@x.y.z` form is the other reason,
and verify sees it first.

## Cannot tell

- **A manifest pins another manager.** A `yarn@` or `pnpm@` value is a deliberate choice about
  how that project installs, and this step neither reverses it nor writes an npm pin alongside.
- **A manifest carries a `packageManager` this step does not recognise** — a range rather than
  an exact version, a bare major, a value that is not a string. Somebody typed it for a reason
  and replacing it is a different decision from filling in a blank. Correct it by hand and
  re-run, or record `declined` with that reason.
- **The repo names two different npm versions and a third manifest has none.** Which of them a
  new manifest should carry is a question the repo itself does not answer, so the step names
  both and writes nothing. Settle on one version across the repo and re-run, which records
  `applied`; record `declined` if the two are deliberate and the manifests genuinely install
  apart.
- **No manifest in the repo names any npm version.** There is nothing to copy, and the step will
  not pick one. Resolve the current stable with `npm view npm version`, check it against what the
  other repos here pin rather than taking it on sight, add the chosen value to one manifest and
  re-run — every other manifest then copies it. Record `declined` if this project is meant to
  install under whatever npm is to hand.

## Fetch before running

This step rewrites a committed `package.json`, adding one key. The `/adopt` procedure refuses to
start on a branch behind its upstream, which is the gate that matters: the other machine may
have added the same key with a different version, and two adds conflict rather than one
silently winning. If the manifest still differs from `@{upstream}` afterwards, compare
`git show @{upstream}:<manifest>` against what is on disk and keep one version per repo.

## Verify

Every project manifest carries `packageManager` matching `npm@` plus a three-part version.

It asserts the pinned form and never a particular version. The spread across this fleet is not a
shape violation — the pin is bumped deliberately, so encoding today's number would turn every
adopted repo into an `audit` failure the day the next npm ships.

It cannot pass vacuously. A repo holding no manifest is exit 2 with that as the reason rather
than exit 0: "every manifest pins the manager" is true of a repo holding none, and an `applied`
line there would claim work in a repo the convention never reaches. Probe answers that case with
positive evidence and the line is recorded `n/a`.

## By hand, after the script

- Run `corepack enable npm` once on each machine that builds this project. Plain
  `corepack enable` shims yarn and pnpm only — npm is a deliberate exception — so without the
  explicit form the pin is silently ignored and `npm -v` keeps reporting the bundled version.
  On Windows that command needs an elevated shell when Node sits under Program Files.
- Check `npm -v` inside the project reports the pinned version. That is the only proof the shim
  took; the field being present proves the intent and not the effect.
- Check the pinned npm can run on the Node this project targets. npm 12 requires Node
  `^22.22.2 || ^24.15.0 || >=26.0.0`, so a project pinned to an earlier Node 24 patch needs an
  npm 11 pin instead — v7's range and this field have to be compatible, and no script here
  compares them.
- Run `npm install` once and commit whatever the lockfile does. The first install under a
  different manager version is the last metadata churn this repo should see.
