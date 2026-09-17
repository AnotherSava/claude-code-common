---
title: A commit gate runs what the deploy runs
---

## What changed

A commit gate is one file, `.claude/commit-checks.sh`, run from the repo root by `/commit` before it
will draft a commit plan. A non-zero exit stops the commit and hands the failures back. That is the
whole mechanism, and it is the only thing in these repos that reads the change before it reaches
`main`: across the fleet's fifteen repos, the last forty commits — the whole history where it is
shorter than that — held zero merge commits when this version was written, so every one of them
commits straight to `main` and every one meets the precondition the rule in `CLAUDE.md` names. The
two global git hooks do not close that gap: the pre-commit hook checks that `config/publish.env` is
marked for encryption, and the pre-push hook checks authorship and signatures. Neither compiles,
type-checks or runs anything.

The convention is not "the file exists". It is the Refactoring Safety rule in `CLAUDE.md`: know
which command is the real gate, and run *that* one — tests and lint usually are not it. A suite
proves behaviour and a linter proves style, and neither type-checks, so a change can pass both and
fail the build. Two traps make a plausible-looking gate dishonest. A checker invoked outside the
build can be structurally blind, because a framework that emits types during the build leaves a bare
`tsc --noEmit` unable to resolve them, and the real errors vanish with the phantom ones. The same
tool pointed at a different config is differently scoped rather than weaker, and it reports success
just as confidently — which is how a type error reached `main` in tauri-dashboard with two hand-run
checks green.

This one is judgement only. It hands the checker nothing, because the clause that decides it — *runs
whatever actually gates the deploy* — is not something a rule can read, and asserting that the file
exists would hand an empty stub a passing line. It is the last of the baseline sweep, so every
answer a machine could supply is already behind the reader before this question.

## Migrating an existing repo

The whole of this version is a question for the user, put in every repo that has not answered it
yet:

> What actually gates a commit here — a build, a lint, a test suite, a schema check — and does
> `.claude/commit-checks.sh` run it? A file that exists but runs nothing is worse than none, because
> `/commit` reports it green.

Where the answer is to write the gate, write it, and keep the reason in the file: every repo that
has one carries a header saying what it runs, why, and what a pass does not cover; that header is
what stops the next reader trusting it for more than it checks. Where the answer is that nothing a
machine can run would say anything about a change here, no file is written — a gate that exits 0
without checking anything is the failure this asks about — and the decision goes into the repo's
project memory as well, so the offer is not re-raised in a later session. That is the "one offer per
project" half of the Best-Practice Adoption rule in `CLAUDE.md`.

A `test` script in a `package.json` is not evidence either way, in the direction that matters here:
it says a suite exists, never that the suite is what would have caught the last thing to break. That
is why this asks rather than reads.

Six repos answered yes when this version was written, and what each runs is worth reading before
answering for a repo that has nothing:

- landlord — `bash tests/run`, the whole suite the README points at rather than a cheaper subset.
  Its `tests/facts.py` re-verifies Caddy grammar against the real binary, and `caddy` and `openssl`
  missing from PATH fail rather than skip. The file's own header says what a pass does not cover:
  nothing on the box, which `bin/selfcheck` covers on a timer there.
- printlab — the shared ingress lint, a guard asserting the running Node against `web/.nvmrc` at the
  precision the pin states, a guard reading the installed better-sqlite3 binary for the symbol that
  aborts on Node 24.19 and later, then ESLint at `--max-warnings=0`, `tsc --noEmit`, vitest, and
  `next build`.
- scheduler — the ingress lint, ESLint at `--max-warnings=0`, vitest, and `next build`. Its
  `typecheck` script is deliberately absent, because the build type-checks against the same
  generated route types and running both buys nothing.
- tauri-dashboard — `npm run check`, `cargo check --all-targets` under `RUSTFLAGS="-D warnings"`,
  `cargo test --lib`, `npm run build`, and the figure check from the docs workflow. The rule written
  into it is to keep these identical to the workflows under `.github/workflows/`, in the same order,
  both ways: a check added there belongs in the gate too.
- tripit — a name-consistency check, because the repo directory and the tenant differ; then the
  ingress lint, ESLint, vitest, and `next build`.
- what-is-next — the ingress lint, a check that the vhost `config/publish.env` names still exists
  (only on a machine that publishes), `npm run typecheck`, and vitest.

Nine had none, and what each holds if the answer is to write one:

- bga-assistant — `build.yml` already runs `npm ci`, `npm run lint` (which is `tsc --noEmit`),
  `npm run build` and `npm test`. A gate here front-runs the workflow rather than inventing a check.
- chrome-assistant — the same four scripts and no workflow at all, so nothing reads a change here
  before `main` does.
- claude, this repo — `claude/tests/memos.py`, `claude/tests/ingress-lint.py`, and the authoring gate
  for the convention versions themselves. Nothing ran any of them on the way to a commit.
- homebrew-tap — the two brew commands named below.
- jsonl-logs-intellij-plugin — a Gradle build with tests under `src/test`, and no workflow.
- toolbox — pytest configured in `pyproject.toml`, with per-tool suites under `tools/*/tst/`.
- transcripts — nothing that builds or tests.
- travel-map — `publish.yml` builds the site and verifies the live result, plus Python under
  `scripts/` with its own `requirements.txt`.
- travel — pytest and ruff both configured in `pyproject.toml`, with eight test modules under
  `tests/`.

Afterwards, in a repo that has a gate:

- Run `bash .claude/commit-checks.sh` and read what it prints. A step it skipped must say so out
  loud — the four web repos print `SKIPPED` with the reason when the shared ingress linter is not on
  this machine — because a skip that looks like a pass is the failure this whole file exists to
  avoid.
- Break something the gate claims to cover, run it again, and confirm it exits non-zero. A gate
  nobody has seen fail is one nobody has seen work.
- Compare the commands against what the deploy or the CI workflow actually runs, command by command.
  Equivalent-looking is not the test; a differently-scoped invocation of the same tool passes while
  the real one fails.
- Keep a gate that duplicates a CI workflow level with it. When the workflow changes, the gate
  changes with it, or the two disagree about what `main` requires and the stricter one is whichever
  the session happened to run.
- Watch CI after the push rather than reporting the local gate as if it were the build. It proves
  the change passes here and says nothing about what the runner does with it.

## When it does not apply

Nothing a machine can run would say anything about a change here, so a gate would be a file that
exits 0 without checking anything. That is an answer a human gives, with the reason named, and never
one read off the repo.

Two repos were the plausible cases when this version was written. The homebrew-tap repo ships Casks
— no build, no test suite, no deploy — though its CI already runs `brew style --cask` and
`brew audit --cask --strict --online` on every push to `main`, so "nothing to run" is a decision
about whether those two belong locally, not an automatic answer. The transcripts repo is a data
pipeline of Python and shell under `bin/`, with no test suite and nothing that builds.

## Continuing rule

None — this is a one-time migration.
