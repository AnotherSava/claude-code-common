---
title: The Node toolchain is declared, enforced and pinned
rules: node-engines, engine-strict, package-manager-pin
---

## What changed

Three properties of a Node project, in the order they depend on each other: say which Node it
targets, make that answer binding rather than advisory, and pin the tool that installs against it.

**Declare the range.** A project says which Node it targets in two places and they do different
jobs. The `.nvmrc` tells a developer's shell what to install; `engines.node` in `package.json` tells
npm, CI, a container build and every tool that reads a manifest. A project carrying only the first
builds on whatever runtime the machine happened to have. Nothing here invents a version: the range
is derived from the `.nvmrc` sitting beside the manifest, and a manifest with no `.nvmrc` beside it
is a question — "24" and a deliberate older pin read identically from a file that does not exist.

**Make it binding.** npm reads `engines` and then installs anyway. The range is advisory by default:
npm prints a warning into a wall of install output and carries on, so a project's `engines.node`,
its `.nvmrc` and its base image can all agree while somebody quietly builds on another runtime. The
failure then surfaces far from its cause — one wrong-runtime install presented as 245
unrelated-looking TypeScript errors rather than as a version complaint. Setting `engine-strict=true`
in the `.npmrc` beside the manifest makes npm exit with `EBADENGINE` instead.

**Pin the manager.** Two machines running different npm versions rewrite the lockfile against each
other. The diff touches no real dependency and only metadata — `"peer": true` markers appearing and
disappearing, `devOptional` flipping to `dev`, optional packages pruned and restored — and it recurs
on every install until the manager is pinned. Corepack reads `packageManager` and shims the manager
to exactly that version, so the pin is what makes two checkouts agree.

The second depends on the first: a project declaring no range has nothing for npm to enforce, so the
range is written before the flag. That ordering used to be two version numbers and is now two steps
inside one walk, which is the same guarantee without a repo able to sit between them.

## Which files this is about

**The manifests.** A repo whose app lives under `web/` also carries `web/.next/package.json`,
sometimes `web/.next/standalone/package.json`, and one manifest per installed dependency under
`node_modules/`. A plain `find` returns all of them. The set that counts is the one
`claude/conventions/rules/_node.py` derives: a walk that never descends into a directory a build
tool or a package manager owns, minus the paths git hides, so every rule that reads a manifest
agrees about which files they are talking about. Ask git what it hides through
`_git.ignored_untracked`, the index-consulting form, so a force-added file inside an ignored
directory still counts.

Every manifest that survives that walk is a project's, and each is asserted on its own. A repo
holding two of them — an app and a helper with its own lockfile — must satisfy all three properties
in both, or say why not.

**The `.npmrc`.** The one beside `package.json`, never one higher up the tree. npm resolves the
project config from the directory that holds the manifest, so a file at a repo root is not read at
all when npm runs in `web/`. A repo with two manifests needs two of them.

**A git that will not answer which paths it hides stops the work**, at any step. An unanswered
question is not an empty skip set. A manifest that is not valid JSON stops it too — that is a broken
file, not an unobservable shape.

## Migrating an existing repo

**The prerequisite is one walk: does this repo hold a `package.json` a person maintains?** If it
does not, none of the three steps applies and the version is a no-op. If it does, every step below
is evaluated against that same set.

Fetch first, and do not run this on a branch behind its upstream. Each step rewrites a committed
file — two of them add a key to `package.json`, one appends to `.npmrc` — and the other machine may
have written the same key with a different value. Where a file still differs from `@{upstream}`
afterwards, compare `git show @{upstream}:<path>` against what is on disk and keep one answer per
repo.

Take the steps in order, and stop the whole repo at the first one that raises a question rather than
half-applying it. Writing one step while another is blocked leaves a continuing rule failing
immediately afterwards with half the change already made.

### 1. Declare `engines.node`

There is work here when a project manifest declares no range and an `.nvmrc` beside it names a
version whose major can be read. Write `>=<major> <<major+1>`, the form the rest of the fleet uses.

Questions rather than work:

- **No range and no readable `.nvmrc`.** Which Node this project targets is written nowhere in the
  repo, and the current LTS is a default for a new project rather than a claim about an existing
  one. Ask for the `.nvmrc`, or for a statement that the project deliberately targets no particular
  runtime.
- **A range and no `.nvmrc`.** The declaration is there and the thing a developer's shell reads is
  not. Which version belongs in that file is not derivable from a range — `>=24` admits every 24.x.
- **The two disagree.** An `.nvmrc` naming a version the declared range excludes is a real
  contradiction and either side could be wrong. Read a partial `.nvmrc` such as `24` as 24.0.0, the
  lowest runtime that pin permits, because a range the lowest permitted version fails is a range the
  pin does not guarantee.
- **A range that will not parse.** Hyphen ranges, prerelease tags and `lts/*` are all real things to
  write and none is a comparator set. Report the range unread rather than assuming it agrees.

### 2. Set `engine-strict=true`

There is work here when a manifest declares `engines.node` — after step 1, that is every project
manifest — and the `.npmrc` beside it does not set the flag, either because there is no such file or
because the file says nothing about the key. Create it beside the manifest where it is missing.

Questions rather than work:

- **An `.npmrc` sets `engine-strict=false` explicitly.** A deliberate opt-out somebody wrote for a
  reason — a dependency whose prebuild targets a different Node, an install known to be good anyway
  — and this version never reverses one. Ask whether the line is stale.
- **An `.npmrc` is there and cannot be read.** Appending to a file whose current content is unknown
  would drop whatever it holds.

### 3. Pin `packageManager`

There is work here when a project manifest carries no `packageManager` field and exactly one npm
version is named elsewhere in the repo to copy. Show the concrete number and where it came from —
"copied from web/package.json" — and ask before writing, so the value reaches the user on screen
rather than as an abstract question.

**Where the version comes from: this repo, or the user — never the network and never a constant.**
Resolving at run time would write a different answer into every repo it visited; a constant is the
same guess with a longer shelf life. A repo running one manifest at `npm@11.17.0` must not gain a
second at some newer number, because the two would install against two lockfiles with two managers.
The fleet's own spread — printlab at 11.17.0 while bga-assistant, scheduler, tripit and
what-is-next are at 11.18.0 — is exactly what that protects. An earlier draft carried the
then-current stable as a constant and wrote it, which measured a *major* above every pin in the
fleet and above the npm this machine runs, so Corepack would have fetched npm 12 and the first
install would have rewritten the lockfile — the exact churn this exists to end.

Hiding matters twice at this step: an ignored manifest is not only a place a pin could be written
but a place one could be *copied from*, and a repo whose tracked manifest lacks a pin must not take
its version from a scratch clone.

Questions rather than work:

- **A manifest pins another manager.** A `yarn@` or `pnpm@` value is a deliberate choice about how
  that project installs, and this neither reverses it nor writes an npm pin alongside.
- **A `packageManager` that will not parse** — a range rather than an exact version, a bare major, a
  value that is not a string. Somebody typed it for a reason and replacing it is a different
  decision from filling in a blank.
- **The repo names two different npm versions and a third manifest has none.** Which of them a new
  manifest should carry is a question the repo does not answer. Settling on one version across the
  repo is what unblocks it.
- **No manifest names any npm version.** There is nothing to copy and this picks none. Resolve the
  current stable with `npm view npm version`, check it against what the other repos here pin rather
  than taking it on sight, and ask for the chosen value.

## Afterwards

- **Run `corepack enable npm` once on each machine that builds this project.** Plain
  `corepack enable` shims yarn and pnpm only — npm is a deliberate exception — so without the
  explicit form the pin is silently ignored and `npm -v` keeps reporting the bundled version. On
  Windows that needs an elevated shell when Node sits under Program Files. Then check `npm -v`
  inside the project reports the pinned version: that is the only proof the shim took, since the
  field being present proves the intent and not the effect.
- **Check the pinned npm can run on the Node this project targets.** npm 12 requires Node
  `^22.22.2 || ^24.15.0 || >=26.0.0`, so a project pinned to an earlier Node 24 patch needs an npm 11
  pin instead. The declared range and this field have to be compatible, and no rule compares them.
- **Check what actually installs Node** — a Dockerfile's base image, a CI workflow's `setup-node`, a
  hosting platform's runtime setting. The files in the repo agreeing with each other is the whole of
  what is asserted; nothing in a manifest can say what a build image ships, and a `node:22-alpine`
  under a `>=24` range now fails its install, which is the point, but it fails in CI rather than
  here.
- **Run `git check-ignore -v <path>/.npmrc`.** A `.gitignore` entry for `.npmrc` is common, because
  the file is where an auth token would sit — and an ignored `.npmrc` means the flag exists on this
  machine and nowhere else, which is the failure this is about. Check the file holds no credential
  before committing it: the migration only appends its own comment and one line, but a file it
  appended to may already carry a registry token.
- **Read the range that was written.** `>=24 <25` is the fleet's shape and pins the major
  deliberately; a project that genuinely wants the next major as soon as it ships wants `>=24`
  instead, and that is an edit, not a defect. Where the question was a missing `.nvmrc`, write the
  full version rather than the major when the project is sensitive to a patch level — one dependency
  in this fleet compiles differently against Node 24.19 headers than against 24.15.
- **Run `npm install` once and commit whatever the lockfile does.** The first install under a
  different manager version is the last metadata churn this repo should see.

## When it does not apply

The tree holds no `package.json` a person maintains — none outside the generated directories, and
none that git does not hide. That is positive evidence read off a walk of the whole repo rather than
off one path's absence: there is no Node project here, so there is no range to declare, nothing for
npm to enforce, and no manager that could drift. A manifest git hides is nobody's to edit, and the
global convention puts scratch in a gitignored `tmp/`, so a clone sitting in one is a designed
condition rather than an accident.

A repo where every project manifest already declares a range its `.nvmrc` admits, has
`engine-strict=true` beside it, and carries a pin in the `npm@x.y.z` form is the other reason.

## Continuing rule

`node-engines` — every project manifest declares `engines.node`, an `.nvmrc` sits beside it, and the
version that `.nvmrc` names falls inside the declared range. It asserts agreement between the two
files and never a particular major: a check for "is it 24" would fail the whole fleet the day the
LTS line moves, and a permanent false alarm is how a real finding stops being read.

`engine-strict` — for every project manifest declaring `engines.node`, the `.npmrc` beside it sets
`engine-strict=true`. The value is read the way npm reads an ini file: comment lines are skipped and
the last assignment wins, so a file setting the key twice is answered the way npm would answer it.

`package-manager-pin` — every project manifest carries `packageManager` matching `npm@` plus a
three-part version. It asserts the pinned form and never a particular version: the spread across
this fleet is not a shape violation, and encoding today's number would fail every adopted repo the
day the next npm ships.
