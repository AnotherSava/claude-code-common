---
version: 8
slug: engine-strict
title: The engines range is enforced, not advisory
scope: repo
---

# The engines range is enforced, not advisory

npm reads `engines` and then installs anyway. The range is advisory by default: npm prints a
warning into a wall of install output and carries on, so a project's `engines.node`, its
`.nvmrc` and its base image can all agree while somebody quietly builds on another runtime. The
failure then surfaces far from its cause — one wrong-runtime install presented as 245
unrelated-looking TypeScript errors rather than as a version complaint. Setting
`engine-strict=true` in the `.npmrc` beside the manifest makes npm exit with `EBADENGINE`
instead.

Only a manifest that declares `engines.node` is in scope, because a project declaring no range
has nothing for npm to enforce. That is what makes the order behind v7 a dependency rather than
a preference: a repo walked here first records that it has no range to enforce, and v7 hands it
one straight afterwards.

## Which .npmrc counts

The one beside `package.json`, never one higher up the tree. npm resolves the project config
from the directory that holds the manifest, so a file at a repo root is not read at all when npm
runs in `web/`. A repo with two manifests needs two of them.

The set of manifests is the one `node_manifests.py` derives, shared with v7 and v9, so a
generated `web/.next/package.json` is not something any of the three tries to enforce a range in.

## Applies when

A project `package.json` declares `engines.node` and the `.npmrc` beside it does not set
`engine-strict=true` — either because there is no such file, or because the file exists and says
nothing about the key.

## Does not apply when

No manifest in this repo declares `engines.node`. That is positive evidence: every project
manifest was read and none carries a range, so there is nothing for npm to enforce and an
`.npmrc` written here would enforce nothing. A repo with no manifest at all reaches the same
answer by the same reading.

A repo where every declaring manifest already has the flag beside it is the other reason. Verify
sees that first and records it without touching anything.

## Cannot tell

- **An `.npmrc` sets `engine-strict=false` explicitly.** That is a deliberate opt-out somebody
  wrote for a reason — a dependency whose prebuild targets a different Node, an install known to
  be good anyway — and this step never reverses one. Remove the line if it is stale and re-run,
  or record `declined` with the reason it is there.
- **An `.npmrc` is there and cannot be read.** Appending to a file whose current content is
  unknown would drop whatever it holds, so the step stops and names it.

Where a repo has several declaring manifests and any one of them hits either case, the whole
repo goes to the question. Writing the flag beside some of them would leave verify failing
straight afterwards, which stops the `/adopt` run with half the change already written.

## Fetch before running

This step appends to a committed `.npmrc` where one exists. The `/adopt` procedure refuses to
start on a branch behind its upstream, which is the gate that matters: the other machine may
have added the same line, and two appends conflict rather than one silently winning. Where the
file did not exist, the step creates it, and a `.gitignore` hiding `.npmrc` would leave that
creation untracked — the check below is what catches it.

## Verify

For every project manifest declaring `engines.node`, the `.npmrc` beside it sets
`engine-strict=true`. Re-derived from disk per manifest, so a repo with two manifests must
satisfy it for both. The value is read the way npm reads an ini file: comment lines are skipped
and the last assignment wins, so a file setting the key twice is answered the way npm would
answer it.

It cannot pass vacuously. A repo where no manifest declares a range is exit 2 with that as the
reason rather than exit 0 — "every declaring manifest enforces its range" is true of a repo
declaring none, and an `applied` line there would claim work this step never did. Probe answers
that case with positive evidence and the line is recorded `n/a`.

## By hand, after the script

- Run `git check-ignore -v <path>/.npmrc`. A `.gitignore` entry for `.npmrc` is common, because
  the file is where an auth token would sit — and an ignored `.npmrc` means the flag exists on
  this machine and nowhere else, which is the failure this convention is about.
- Check the file holds no credential before committing it. This step only ever appends its own
  comment and one line, but a file it appended to may already carry a registry token, and that
  belongs in the environment rather than in the repo.
- Run an install once. The flag changes what npm does rather than what it says, so the proof is
  an install that refuses under the wrong runtime, and this machine may be the right one either
  way.
- Check what CI and the container build install. `engine-strict` binds npm, not a base image: a
  Dockerfile on `node:22-alpine` under a `>=24` range now fails its install, which is the point,
  but it fails in CI rather than here.
