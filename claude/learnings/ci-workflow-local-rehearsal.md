# Rehearsing a CI workflow before its first push

A workflow's first run happens on a push, so a mistake in it is already published history plus a red
build on a commit that was fine. The cost of finding out beforehand is one container.

The method: run the workflow's own commands in an image pinned to the same runtime the workflow asks
for, from a clone made **inside** the container. It is not a substitute for the runner — no
`actions/*` step runs, and the runner's own environment differs — but it answers the questions a
workflow actually gets wrong: does the install work on that platform, does the test suite pass
against that platform's tools, and is the version the workflow believes it pinned the version it
gets.

```bash
docker run --rm -v "$PWD":/src:ro node:24.19.0 bash -c '
  set -e
  git clone -q /src /w 2>/dev/null; cd /w/web
  corepack enable npm >/dev/null 2>&1
  echo "node $(node -v) | npm $(npm -v) | $(tar --version | head -1)"
  npm ci --no-audit --no-fund >/dev/null && echo "npm ci  OK"
  npm run lint -- --max-warnings=0 >/dev/null && echo "lint    OK"
  npm test >/tmp/t.log 2>&1 && echo "tests   OK"
  npm run build >/tmp/b.log 2>&1 && echo "build   OK"
'
```

## Clone inside the container; do not mount the installed tree

Mounting a working directory that already has `node_modules` fails, and the error points at a
dependency rather than at the mount:

```
Require stack:
- /w/node_modules/rolldown/dist/shared/binding-<hash>.mjs
```

Native binaries are per-platform, so a macOS install cannot run on Linux. Mounting the repo
read-only and cloning from it inside the container gives a clean tree that the container's own
`npm ci` then populates correctly — which is also closer to what the runner does.

A clone also means the rehearsal tests **HEAD**, not the dirty working tree. Where the workflow file
itself is the only uncommitted change that is exactly right; where the code under test is
uncommitted too, commit it first or the rehearsal is about something else.

## The bind mount may expose nothing, and the symptom accuses the project

Docker Desktop on macOS shares a configured list of paths — the home directory among them, and
**not** `/private/tmp`. A mount outside that list produces an empty directory rather than an error,
and the command then fails in a way that reads as a project fault:

```
npm warn exec The following package was not found and will be installed: vitest@5.0.3
No test files found, exiting with code 1
include: **/*.{test,spec}.?(c|m)[jt]s?(x)
```

Two tells, both of which point at the mount: `npx` **downloading** a tool the project depends on,
and the test runner reporting its *default* include pattern rather than the project's. Measured
2026-10-08 against a `git worktree` under `/tmp` — which macOS resolves to `/private/tmp`. Keep the
rehearsal inside the home directory, or confirm the path is shared before reading the output.

## What a rehearsal is worth: a measurement that was right locally and wrong on the runner

The case that justified the container. A project pinning `"packageManager": "npm@<version>"` had a
`corepack enable` step, and `npm -v` on the development machine reported the pinned version — so the
step looked proven. In the container it reported the version bundled with Node instead: the host had
that npm for unrelated reasons, and the step had never been doing anything.

The general shape: **a check that reads the same on the runner and on your machine proves nothing if
your machine would pass it anyway.** Prefer a measurement taken somewhere that has no prior reason
to agree with you.

## Verify the action majors and their inputs, do not recall them

Actions move faster than memory: `actions/checkout` and `actions/setup-node` were both on **v7** in
October 2026, where a workflow written from recollection says `@v4`. `github-action-version-bumps.md`
has the procedure for reading the current major and judging the breaking notes. One addition for a
workflow being written rather than bumped — confirm every input you are about to use still exists at
that major, from the action's own `action.yml`:

```bash
gh api repos/actions/setup-node/contents/action.yml --jq .content | base64 -d |
  sed -n '/^inputs:/,/^runs:/p' | grep -E "^  [a-z-]+:"
```

## Say what the workflow cannot cover, in the workflow

Where the local gate is richer than CI — checks that need a private repo, a decryption key, a
database — the workflow file is the place to record which of them it does not run and why. A green
tick is otherwise read as the gate having passed, which is the failure
`memory/feedback_not_run_is_not_pass.md` is about.
