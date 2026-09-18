---
title: The commit gate runs what the deploy runs, and the conventions checker
---

## What changed

A commit gate is one file, `.claude/commit-checks.sh`, run from the repo root by `/commit` before it
will draft a commit plan. A non-zero exit stops the commit and hands the failures back. That is the
whole mechanism, and it is the only thing in these repos that reads a change before it reaches
`main`: across the fleet's fifteen repos, the last forty commits — the whole history where it is
shorter — held zero merge commits when this was written, so every one commits straight to `main`.
The two global git hooks do not close that gap: the pre-commit hook checks that `config/publish.env`
is marked for encryption, and the pre-push hook checks authorship and signatures. Neither compiles,
type-checks or runs anything.

The gate carries two things.

**Whatever actually gates the deploy.** This is the Refactoring Safety rule in `CLAUDE.md`: know
which command is the real gate, and run *that* one — tests and lint usually are not it. A suite
proves behaviour and a linter proves style, and neither type-checks, so a change can pass both and
fail the build. Two traps make a plausible-looking gate dishonest. A checker invoked outside the
build can be structurally blind, because a framework that emits types during the build leaves a bare
`tsc --noEmit` unable to resolve them, and the real errors vanish with the phantom ones. And the same
tool pointed at a different config is differently scoped rather than weaker, reporting success just
as confidently — which is how a type error reached `main` in tauri-dashboard with two hand-run
checks green.

**The conventions checker.** Every rule a repo has taken on is run by `claude/conventions/check.py`,
and nothing invokes that on its own. Until the gate calls it, a repo can adopt every version in the
set and still have each rule measured exactly once — by the walk, on the day it ran — with nothing
looking again afterwards. The migrations would be done and the enforcement nowhere, which is the
half of the design that stops a repo drifting back out of shape between walks.

The second is why **every adopting repo gets a gate**, including one with no build, no suite and no
linter. Such a repo was once entitled to answer "nothing here is worth running" and write no file;
the checker is something a machine can run in every repo that adopts, so that answer is no longer
available. A repo may still have nothing else worth gating, and it now has this.

## Migrating an existing repo

**The prerequisite is nothing — every adopting repo does this.** What varies is only whether the
file already exists.

Where `.claude/commit-checks.sh` does not exist, create it, with a header saying what it runs, why,
and what a pass does not cover. That header is what stops the next reader trusting it for more than
it checks; the dotfiles repo's own file is the worked example.

Add the checker near the top, so a convention violation is reported before the slower suites run:

```sh
python3 ~/.claude/conventions/check.py .
```

The trailing `.` is optional — the checker defaults to the current directory, and a gate runs from
the repo root — but naming it keeps the line explicit about what it checks. The script is reached
through the installed path rather than a checkout path, because only the dotfiles repo has
`claude/conventions/` inside it — there it is
`python3 claude/conventions/check.py .` instead. Wrap it in whatever the file uses to label and
buffer a step; the bare line is enough where there is no such helper.

Then put the other half to the user, in every repo that has not answered it:

> What actually gates a commit here — a build, a lint, a test suite, a schema check — and does
> `.claude/commit-checks.sh` run it? A file that exists but runs nothing is worse than none, because
> `/commit` reports it green.

A `test` script in a `package.json` is not evidence either way, in the direction that matters: it
says a suite exists, never that the suite is what would have caught the last thing to break. That is
why this asks rather than reads.

Six repos had a gate when this was written, and they are worth reading before answering for a repo
that has none — landlord runs the whole suite its README points at, with `caddy` and `openssl`
missing from PATH failing rather than skipping; printlab, scheduler, tripit and what-is-next each
run the shared ingress lint ahead of their own lint, tests and build; tauri-dashboard keeps its gate
identical to the workflows under `.github/workflows/`, in the same order, both ways. Read the files
rather than this paragraph, which was a snapshot when it was written.

Afterwards:

- **Run `bash .claude/commit-checks.sh` and read what it prints.** The checker names every rule it
  took on and every rule it could not measure; a rule reported `UNMEASURED` is not a pass and is the
  thing to settle before moving on. A step that skipped must say so out loud — the four web repos
  print `SKIPPED` with the reason when the shared ingress linter is not on this machine — because a
  skip that looks like a pass is the failure this whole file exists to avoid.
- **Break something the gate claims to cover, run it again, and confirm it exits non-zero.** A gate
  nobody has seen fail is one nobody has seen work.
- **Compare the commands against what the deploy or the CI workflow actually runs, command by
  command.** Equivalent-looking is not the test; a differently-scoped invocation of the same tool
  passes while the real one fails. Keep a gate that duplicates a workflow level with it, or the two
  disagree about what `main` requires and the stricter one is whichever the session happened to run.
- **Watch CI after the push** rather than reporting the local gate as if it were the build. It proves
  the change passes here and says nothing about what the runner does with it.

## When it does not apply

Nowhere this walk reaches, and that is deliberate rather than an omission. A repo that adopts nothing
— a third-party clone, or one carrying an `exempt` record — never gets here at all, because that is
settled before any version is read. Every repo that does adopt takes on rules as its number rises,
so there is no repo for which running the checker is meaningless, and no repo left that can answer
"nothing to run". A gate that exists but never calls the checker is the case this exists to end, not
a condition that excuses it.

## Continuing rule

None, and a rule could not cover either half even in principle. The deploy-gate clause — *runs
whatever actually gates the deploy* — is not something a rule can read, and asserting that the file
exists would hand an empty stub a passing line. A rule asserting that the gate invokes the checker
would itself be run by the checker, so in precisely the repo where the assertion is false it would
never execute.

What catches a later removal is the walk's closing report, which says when this repo's gate does not
run `check.py`, and the gate's own output, which names the rules it took on every time it runs.
