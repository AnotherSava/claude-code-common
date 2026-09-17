---
title: The engines range is enforced, not advisory
rules: engine-strict
---

## What changed

npm reads `engines` and then installs anyway. The range is advisory by default: npm prints a warning
into a wall of install output and carries on, so a project's `engines.node`, its `.nvmrc` and its
base image can all agree while somebody quietly builds on another runtime. The failure then surfaces
far from its cause — one wrong-runtime install presented as 245 unrelated-looking TypeScript errors
rather than as a version complaint. Setting `engine-strict=true` in the `.npmrc` beside the manifest
makes npm exit with `EBADENGINE` instead.

Only a manifest that declares `engines.node` is in scope, because a project declaring no range has
nothing for npm to enforce. That is what makes the order behind the previous version a dependency
rather than a preference: a repo walked here first records that it has no range to enforce, and the
version before this hands it one straight afterwards.

**Which .npmrc counts.** The one beside `package.json`, never one higher up the tree. npm resolves
the project config from the directory that holds the manifest, so a file at a repo root is not read
at all when npm runs in `web/`. A repo with two manifests needs two of them. The set of manifests is
the one `claude/conventions/rules/_node.py` derives, shared with every other rule that reads one, so
a generated `web/.next/package.json` is not something any of them tries to enforce a range in.

## Migrating an existing repo

There is work here when a project `package.json` declares `engines.node` and the `.npmrc` beside it
does not set `engine-strict=true` — either because there is no such file, or because the file exists
and says nothing about the key.

Fetch first, and do not run this on a branch behind its upstream: the migration appends to a
committed `.npmrc` where one exists, and the other machine may have added the same line. Where the
file does not exist, create it beside the manifest.

Two states are a question for the user rather than work to do:

- **An `.npmrc` sets `engine-strict=false` explicitly.** That is a deliberate opt-out somebody wrote
  for a reason — a dependency whose prebuild targets a different Node, an install known to be good
  anyway — and this version never reverses one. Ask whether the line is stale.
- **An `.npmrc` is there and cannot be read.** Appending to a file whose current content is unknown
  would drop whatever it holds, so stop and name it.

Where a repo has several declaring manifests and any one of them hits either case, the whole repo
goes to the question. Writing the flag beside some of them would leave the continuing rule failing
straight afterwards, with half the change already made. A git that will not answer which paths it
hides stops the work too: an unanswered question is not an empty skip set.

Afterwards:

- Run `git check-ignore -v <path>/.npmrc`. A `.gitignore` entry for `.npmrc` is common, because the
  file is where an auth token would sit — and an ignored `.npmrc` means the flag exists on this
  machine and nowhere else, which is the failure this convention is about.
- Check the file holds no credential before committing it. The migration only ever appends its own
  comment and one line, but a file it appended to may already carry a registry token, and that
  belongs in the environment rather than in the repo.
- Run an install once. The flag changes what npm does rather than what it says, so the proof is an
  install that refuses under the wrong runtime, and this machine may be the right one either way.
- Check what CI and the container build install. The flag binds npm, not a base image: a Dockerfile
  on `node:22-alpine` under a `>=24` range now fails its install, which is the point, but it fails
  in CI rather than here.

## When it does not apply

No manifest in this repo declares `engines.node`. That is positive evidence: every project manifest
was read and none carries a range, so there is nothing for npm to enforce and an `.npmrc` written
here would enforce nothing. A repo with no manifest at all reaches the same answer by the same
reading. A manifest git hides is not one of them — a vendored wheel under a gitignored `venv/` ships
its own `engines.node`, and an `.npmrc` written beside it would sit in a tree the next rebuild
deletes.

A repo where every declaring manifest already has the flag beside it is the other reason.

## Continuing rule

`engine-strict` — for every project manifest declaring `engines.node`, the `.npmrc` beside it sets
`engine-strict=true`. The value is read the way npm reads an ini file: comment lines are skipped and
the last assignment wins, so a file setting the key twice is answered the way npm would answer it.
