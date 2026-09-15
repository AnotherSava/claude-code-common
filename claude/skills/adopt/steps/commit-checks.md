---
version: 13
slug: commit-checks
title: A commit gate runs what the deploy runs
scope: repo
---

# A commit gate runs what the deploy runs

A commit gate is one file, `.claude/commit-checks.sh`, run from the repo root by `/commit`
before it will draft a commit plan. A non-zero exit stops the commit and hands the failures
back. That is the whole mechanism, and it is the only thing in these repos that reads the change
before it reaches `main`: across all fifteen, the last forty commits — the whole history where
it is shorter than that — held zero merge commits when this step was written, so every one of
them commits straight to `main` and every one meets the precondition the rule in `CLAUDE.md`
names. The two global git hooks do not close that gap: the pre-commit hook checks that
`config/publish.env` is marked for encryption, and the pre-push hook checks authorship and
signatures. Neither compiles, type-checks or runs anything.

The convention is not "the file exists". It is the Refactoring Safety rule in `CLAUDE.md`: know
which command is the real gate, and run *that* one — tests and lint usually are not it. A suite
proves behaviour and a linter proves style, and neither type-checks, so a change can pass both
and fail the build. Two traps make a plausible-looking gate dishonest. A checker invoked outside
the build can be structurally blind, because a framework that emits types during the build
leaves a bare `tsc --noEmit` unable to resolve them, and the real errors vanish with the phantom
ones. The same tool pointed at a different config is differently scoped rather than weaker, and
it reports success just as confidently — which is how a type error reached `main` in
tauri-dashboard with two hand-run checks green.

This step is judgement only. It ships no script, because the clause that decides it — *runs
whatever actually gates the deploy* — is not something a probe can read, and a verify asserting
that the file exists would hand an empty stub a passing line. It is the last step of the
baseline sweep, so every answer the machine could supply is already behind the reader before
this question.

## Applies when

Every repo, every time, until it holds a line for this version. There is no script, so `/adopt`
treats the step as a permanent probe exit 2 and puts the question below to the user.

## Does not apply when

Nothing a machine can run would say anything about a change here, so a gate would be a file that
exits 0 without checking anything. Record `n/a` with the reason as the note.

Two repos are the plausible cases. The homebrew-tap repo ships Casks — no build, no test suite,
no deploy — though its CI already runs `brew style --cask` and
`brew audit --cask --strict --online` on every push to `main`, so "nothing to run" is a decision
about whether those two belong locally, not an automatic answer. The transcripts repo is a data
pipeline of Python and shell under `bin/`, with no test suite and nothing that builds.

A `test` script in a `package.json` is not evidence either way, in the direction that matters
here: it says a suite exists, never that the suite is what would have caught the last thing to
break. That is why this step asks rather than reads.

## Cannot tell

Always, and the question is this. What actually gates a commit here — a build, a lint, a test
suite, a schema check — and does `.claude/commit-checks.sh` run it? A file that exists but runs
nothing is worse than none, because `/commit` reports it green.

Six repos answered yes when this step was written, and what each runs is worth reading before
answering for a repo that has nothing:

- landlord — `bash tests/run`, the whole suite the README points at rather than a cheaper
  subset. Its `tests/facts.py` re-verifies Caddy grammar against the real binary, and `caddy`
  and `openssl` missing from PATH fail rather than skip. The file's own header says what a pass
  does not cover: nothing on the box, which `bin/selfcheck` covers on a timer there.
- printlab — the shared ingress lint, a guard asserting the running Node against `web/.nvmrc` at
  the precision the pin states, a guard reading the installed better-sqlite3 binary for the
  symbol that aborts on Node 24.19 and later, then ESLint at `--max-warnings=0`, `tsc --noEmit`,
  vitest, and `next build`.
- scheduler — the ingress lint, ESLint at `--max-warnings=0`, vitest, and `next build`. Its
  `typecheck` script is deliberately absent, because the build type-checks against the same
  generated route types and running both buys nothing.
- tauri-dashboard — `npm run check`, `cargo check --all-targets` under
  `RUSTFLAGS="-D warnings"`, `cargo test --lib`, `npm run build`, and the figure check from the
  docs workflow. The rule written into it is to keep these identical to the workflows under
  `.github/workflows/`, in the same order, both ways: a check added here belongs in the workflow
  too.
- tripit — a name-consistency check, because the repo directory and the tenant differ; then the
  ingress lint, ESLint, vitest, and `next build`.
- what-is-next — the ingress lint, a check that the vhost `config/publish.env` names still
  exists (only on a machine that publishes), `npm run typecheck`, and vitest.

Nine had none, and what each holds if the answer is to write one:

- bga-assistant — `build.yml` already runs `npm ci`, `npm run lint` (which is `tsc --noEmit`),
  `npm run build` and `npm test`. A gate here front-runs the workflow rather than inventing a
  check.
- chrome-assistant — the same four scripts and no workflow at all, so nothing reads a change
  here before `main` does.
- claude, this repo — `claude/tests/memos.py`, `claude/tests/ingress-lint.py`, and the authoring
  gate for these steps, `claude/skills/adopt/conventions.py selftest`. Nothing runs any of them
  on the way to a commit.
- homebrew-tap — the two brew commands named above.
- jsonl-logs-intellij-plugin — a Gradle build with tests under `src/test`, and no workflow.
- toolbox — pytest configured in `pyproject.toml`, with per-tool suites under `tools/*/tst/`.
- transcripts — nothing that builds or tests.
- travel-map — `publish.yml` builds the site and verifies the live result, plus Python under
  `scripts/` with its own `requirements.txt`.
- travel — pytest and ruff both configured in `pyproject.toml`, with eight test modules under
  `tests/`.

The answer records `n/a` when nothing here can be gated, or `declined` when something can be and
no gate is being added now. It can never record `applied`: the engine refuses that state for a
step with no verify to run, printing *no verify to run, so it can never be recorded applied*.
Where the answer is to write the gate, write it first and then record the line as `n/a`, with
the note naming the file and the commands it runs — the note is the only durable statement of
what was decided here, so it should read as an answer and not as a shrug.

## Verify

Nothing re-derives this. The step has no script, so `audit` prints
`judgement — not re-checkable` for an `n/a` line and `declined by the user — not re-checked` for
a declined one. Neither is a pass, and neither should be read as one.

What a human checks, in a repo that has a gate:

- Run `bash .claude/commit-checks.sh` and read what it prints. A step it skipped must say so out
  loud — the four web repos print `SKIPPED` with the reason when the shared ingress linter is
  not on this machine — because a skip that looks like a pass is the failure this whole file
  exists to avoid.
- Break something the gate claims to cover, run it again, and confirm it exits non-zero. A gate
  nobody has seen fail is one nobody has seen work.
- Compare the commands against what the deploy or the CI workflow actually runs, command by
  command. Equivalent-looking is not the test; a differently-scoped invocation of the same tool
  passes while the real one fails.

## By hand, after the script

There is no script, so all of it is by hand.

- When the answer is to add a gate, keep the reason in the file. Every one of the six carries a
  header saying what it runs, why, and what a pass does not cover; that header is what stops the
  next reader trusting it for more than it checks.
- When the answer is no, record the decision in the repo's project memory as well as in the
  convention record, so the offer is not re-raised in a later session. That is the "one offer
  per project" half of the Best-Practice Adoption rule in `CLAUDE.md`.
- Keep a gate that duplicates a CI workflow level with it. When the workflow changes, the gate
  changes with it, or the two disagree about what `main` requires and the stricter one is
  whichever the session happened to run.
- Watch CI after the push rather than reporting the local gate as if it were the build. It
  proves the change passes here and says nothing about what the runner does with it.
