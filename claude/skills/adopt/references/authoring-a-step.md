# Authoring version N+1

Read this when a convention in the dotfiles repo has changed and the fleet has to follow. It is the
contract a step owes: the frontmatter, the five headings, the exit codes, the six idempotence rules, the
fixtures, and the two ways a shipped step is corrected without ever being edited.

The trigger is a diff, not a memory. When a change set touches `claude/CLAUDE.md`, `git/gitignore` or
`git/gitattributes` and an added or changed line names a repo-shape token — `.claude/`, `config/`,
`scripts/`, `package.json`, `.npmrc`, `LICENSE`, `commit-checks` — answer one question in writing
before committing it: does this change what an **already-adopted** repo must look like? A yes means the
step is authored now and commits with the change that caused it, because a convention that ships
without its step is one every repo has to be brought to by hand, which is the failure this whole skill
exists to end.

## When a bump is warranted

The test is narrow: **a repo already conforming to the previous version must now do something to
conform.** Not "a rule was reworded", and not "a new rule appeared that no existing repo violates" —
those cost every repo a line of text and buy nothing. A convention that no probe can read is not a step
at all; it belongs in `not-versioned.md` with its reason, so that "current" keeps meaning *every
versionable convention has been decided*.

## Allocating the version

A monotonic integer, one per step, allocated as `max(version) + 1` across `steps/*.md` in this checkout.
Not semver — there is no compatibility axis. Not a date — two steps in one day would have no order.

It lives in the frontmatter and never in the filename: an ordering baked into a name costs a mass rename
to change or extend (`~/.claude/memory/feedback_sort_key_not_in_identifier.md`). `latest` is derived as
`max(version:)`, so there is no `LATEST` file to drift, a duplicate `version:` is a collision the engine
refuses rather than a silent tie, and deleting a prose file silently changes `latest` — step prose is
append-only and never renumbered.

## The files

```
steps/<slug>.md                 prose (required)
steps/<slug>.py                 probe / apply / verify (omit for a judgement-only convention)
steps/fixtures/<slug>/before/          a tree the step applies to
steps/fixtures/<slug>/conformant/      a tree already in the target shape
steps/fixtures/<slug>/<anything-else>/ a tree the step must refuse: apply exits 3 and writes nothing
```

Four modules beside the steps are shared rather than per-step, and an underscore marks the ones that
exist only for this skill. Import them by bare name — `sys.path[0]` is already the steps directory when
the engine runs a script by path:

```
steps/_dispatch.py       the command line every step shares (see Exit codes below)
steps/_gitignore.py      asking git what it ignores, and rewriting a .gitignore reversibly
steps/_own_fixtures.py   the one directory a step walking the tree must refuse to walk
steps/node_manifests.py  which package.json files are a project's, and writing one key into one
```

A step with no `.py` is pure judgement: `/adopt` treats it as a permanent `probe` exit 2 and puts the
question under its `## Cannot tell` heading to the user. Make a step judgement-only when the convention's
target shape contains a clause no script can read — "runs whatever actually gates the deploy" is one —
and not merely because the decision is a human's. A judgement step asks its question in *every* repo, so
it is right only when every repo genuinely needs a human answer, and it ships no fixtures — fixtures
with no script beside them are how `selftest` recognises a script that has gone missing. Where an
assertable shape exists, write the script and push the judgement into a `probe` refusal or into
`## By hand, after the script`; that hands every conformant repo a free `applied` line instead of a
question it has already answered.

## Frontmatter

```yaml
---
version: 7            # int, unique across steps/, allocated max+1
slug: node-engines-declared
title: The Node engines range is declared
scope: repo           # or: machine
script: node-engines-declared.py    # optional; omit for judgement-only
supersedes: 3         # optional; this step corrects step 3, which was wrong
retracted: 9          # optional; step 9 reverses this convention
affects: memo         # optional; tools whose stored data this reshapes, comma-separated
---
```

**`affects:` is how a tool refuses to read a format the repo has not adopted.** Name the tool whose
stored data the step changes, and that tool can ask `conventions.behind_for(root, "<tool>")` for the
one number it needs: is this repo at or above the newest version reshaping me? v1 declares
`affects: memo`, and `memos.py` exits rather than list an empty backlog in a repo whose thirty-three
items are still in the file v1 replaces, or write a new memo beside it.

Declare it whenever a step moves, renames or re-shapes something another script reads — and do not
declare it for a step that only adds a file nothing yet consumes. The alternative a tool reaches for
first is sniffing the old artifact ("does `memos.md` still exist?"); that answers for one migration
and has to be rewritten for the next, while a version comparison keeps working when the format moves
again. The cost is real and worth naming: a tool guarded this way refuses in a conformant repo that
simply has no record yet, which is the intended reading — unrecorded is not the same fact as fine.

A `scope: repo` step records one line, into the committed `.claude/conventions.tsv`. A `scope: machine`
step splits: an `applied` line goes into both that file, which travels and says the repo decided this,
and the gitignored `.claude/conventions.local.tsv`, which does not and says this machine wired it — so a
fresh clone holds the first without the second and reports the step as decided but not wired here. An
`n/a` or a `declined` goes only to the committed file, being a fact about the repo rather than about a
machine. Anything asserted about a path outside the repo is `scope: machine`, always.

The `supersedes:` and `retracted:` fields may not both appear on one step.

## The five mandatory headings

Every `<slug>.md` carries all five, in this order, and `selftest` fails the step if one is missing:

- **`## Applies when`** — the condition `probe` returns 0 on, in prose.
- **`## Does not apply when`** — every condition that is exit 1, each with the positive evidence behind
  it (see below).
- **`## Cannot tell`** — the exit 2 cases, and for each one the question, written as the user will read
  it. For a judgement-only step this heading holds the whole question.
- **`## Verify`** — what the target shape is and how it is asserted from disk. Say what makes it
  non-vacuous.
- **`## By hand, after the script`** — the half of the convention the script deliberately does not
  assert. Never leave this empty to look tidy: it is what stops a recorded note claiming more than was
  checked.

**`## Fetch before running`** is optional and required only for a step that deletes or rewrites a
committed file. It says what could be lost and how to compare against `@{upstream}` afterwards.

## Exit codes

Uniform across every step, and the engine reads nothing else:

| Code | `probe` | `apply` | `verify` |
|---|---|---|---|
| 0 | applies | done, note on stdout | asserted, in the target shape |
| 1 | does not apply, reason on stdout | — never | — never |
| 2 | cannot tell, question on stdout | — never | shape unobservable, reason on stdout |
| 3 | error | stopped; every source artifact intact | not in the target shape, or an assertion failed |

Argument handling is not yours to write. Every step ends with exactly these two lines, and
`steps/_dispatch.py` owns the rest:

```python
if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
```

It strips `--dry-run`, checks the argument count and the command name, absolutizes the repo root, and
wraps the call so an unexpected exception prints its traceback to stderr and returns **3**. A step
carries no foot-of-file guard at all. This is deliberately *not* the hooks' arrangement: a hook owes
the harness `SystemExit(0)` whatever happens, while a step exiting 0 on a crash claims work it did not
do — in the v1 step that code means "applied, source removed". A second `apply` on an already-applied
repo must exit 0 or 3 and never crash: the design's reference step raised `FileNotFoundError` and
exited 1, a code that means "does not apply" everywhere else, and the idempotence assertion written to
catch that is the thing that tripped over it.

Shared because the exit codes are a vocabulary rather than a status, so twelve hand-written copies of
the same sixteen lines were twelve chances for the next author to return 1 on a usage error and have a
repo silently recorded "does not apply". `cmd_apply` therefore takes `(root, dry_run)` in every step,
including the ones that write nothing either way — those ignore the flag and say so in their own
docstring, which keeps all the signatures one shape.

### `probe` exit 1 needs positive evidence, never absence of evidence

"No `package.json` anywhere in this repo" is positive evidence a Node convention does not apply. "This
repo has no `.claude/memos/` and no `.claude/memos.md`" is *not* evidence that it does not want a
backlog — four repos in the fleet have deliberately never kept one, and that is indistinguishable by
probe from a migration nobody got to. That case is exit 2 with a printed question.

A wrong step is worse than a missing one. A missing step leaves every repo in one known state; a wrong
one, already run across the fleet, scatters those repos into states no later step recognises. **`probe`
may refuse; `apply` may never guess.** That also means never resolving a value over the network — a version
`npm view` would answer is a question for the user, not a lookup.

### `verify` asserts the target SHAPE, never the migration's history

A step's `verify` answers one question: *is this repo in the shape this convention requires?* It does
not answer *did a migration run here*. Four repos that committed the memos migration would have been
recorded `n/a — does not apply` under the other reading, because the evidence a history check wants is
exactly what the adoption commit destroys.

So: exit 3 on a repo not in the target shape, 0 on a repo in it, 2 only when the shape itself is
unobservable, and never 1. **It must never pass vacuously** — a `verify` returning 0 on an empty
directory is a broken step, and `selftest` asserts against precisely that using the step's own `before/`
fixture.

### The per-item assertion lives in `apply`

Assert per item, never on a count (`~/.claude/learnings/git-stash-pull-safety.md`): zero hits means the
item was lost, two means it was migrated twice, and a tally passes the moment one of each happens. That
assertion runs inside `apply`, in the same process, **before** it removes any source — not in `verify`,
whose evidence the adoption commit erases, leaving the same command printing `NOT COVERED` for a line
written a minute earlier.

What `apply` prints is the per-item result, and its last line is a one-sentence summary; that sentence
becomes the record's note, which is the only place the assertion is durable.

## The idempotence contract

Six rules, and `selftest` enforces what it can of them:

1. `apply` reaches the same end state from a clean run, a re-run, and a half-finished run.
2. It fails closed — every source artifact survives every failure — and exits 3.
3. It never removes a source before per-item verification of the destination passes in the same process.
4. It never commits, never touches the network, never forks per item, never calls `ln -s` (Git Bash
   silently makes a copy, leaving a machine that looks wired and is not), and writes `newline="\n"` on
   every file it opens.
5. `verify` re-derives the target shape from disk. It must fail on a tree that is not in that shape,
   proven per step by the `before/` fixture.
6. A parser that recognises items must **abort rather than skip**.

### Rule 6, and the case that put it there

Any content line a parser cannot classify stops the step at exit 3 and is printed verbatim. Do not skip
it, do not log it and continue, and do not fall back to a looser pattern.

The design's own reference step matched one checklist shape with a regex and ignored every line that did
not match. Against a real 33-item backlog it silently dropped four line shapes, wrote the rest, ran its
per-item check over only the lines it had recognised, deleted the source file, and reported "each
asserted present exactly once". Every part of that sentence was true about the items it knew about, and
the four it never saw were gone. A parser that skips is a parser whose verification is scoped to its own
blind spots.

## Fixtures

Two trees per step at minimum, and `before/` is the one that does the work:

- **`before/`** — a tree the step applies to, where `probe` exits 0, `apply` transforms it, and `verify`
  on an untouched copy **must fail**. That last assertion is the only one proving a `verify` can tell
  done from never-run.
- **`conformant/`** — a tree already in the target shape, where `verify` exits 0 with no mutation. That
  is the path most repos in the fleet actually take.
- **Any further tree** — one the step must refuse, where `apply` exits 3 and writes nothing. Rule 6 is
  the rule with a real loss behind it and `before/` structurally cannot carry it: `before/` is the tree
  apply has to transform, so a line that stops apply there would turn the gate red. The v1 step's
  `unclassifiable/` is the worked example — a backlog carrying the four line shapes its first draft
  silently dropped.

Build the fixture from a real repo's shape rather than an invented one — the em-dash separator that made
four memos read as `LOST` only appeared because the fixture carried a real backlog's punctuation. Never
copy anything private into a fixture; a step's fixture ships in a public repo. A synthetic fixture is not
automatically safe either: v12's carried a real box's hostname in an otherwise invented file, and the
confidentiality scan that looks for addresses and absolute paths does not catch a bare name.

**A fixture cannot sit at a path the pre-commit hook guards.** That hook refuses a plaintext
`config/publish.env` or `*.secret.md` anywhere in the tree, and it is right to — it cannot tell a
fixture from the real thing, and the version that could would be the version that waves the real thing
through. So v12 has no `config/publish.env` in either tree, deliberately: it was written, refused at
commit, and measured to be worth nothing (227 assertions passed identically with and without it) because
that step infers co-tenancy from the compose file anyway. If a future step genuinely needs a fixture at a
guarded path, change the step's detection or the fixture's shape — do not reach for `--no-verify`.

### A step that walks the tree must skip this directory

The dotfiles repo is itself in the fleet, so every step eventually runs against the checkout holding
`steps/fixtures/` — and those trees are deliberately broken. A step that enumerates its subject by
walking, or by asking `git ls-files`, reads them as findings about this repo. Measured before the guard
existed: the Node steps listed nine fixture manifests and so could never return 0 here, and the
gitignore-scope step's `probe` exited 0 on a list where one real finding sat among five fixture ones —
a dry run that reads plausible, gets approved, and rewrites the trees `selftest` gates on.

Call `_own_fixtures.prune(base, dirs)` inside an `os.walk`, or `_own_fixtures.is_beneath(path)` on a
flat path list. Do not skip every directory *named* `fixtures`: that also hides a project's real
`tests/fixtures/`, and the test has to be identity so it still fires through the `~/.claude/skills/`
symlink and still stays quiet inside a scratch copy, where the fixture is the repo under test and must
be read in full.

Identity there means `os.path.samefile`, not two `realpath` strings compared. `realpath` resolves
symlinks and does not canonicalise case, so on this machine the guard answered False on every run —
the symlink is spelled `projects`, `/adopt` passes `Projects`, and the volume folds the difference —
and every walking step read its own fixtures as findings about the dotfiles repo anyway, which is the
state this section was written to prevent. That is the trap
`learnings/comparing-paths-symlinks-and-case.md` opens on, and the fix is one call.

### And it must ask git what it hides

`_own_fixtures` answers one hazard by identity. The other is that a name rule cannot see a scratch
clone: the global convention puts scratch in a gitignored `tmp/`, so a `package.json` or a compose
file inside one is a designed and recurring condition rather than an accident. Measured 2026-09-15 —
two repos in the fleet had their only manifest inside a gitignored `venv/`, and v8's probe exited 0
on both, so an approved walk would have written an `.npmrc` into a virtualenv the next rebuild
deletes and recorded `applied` on evidence no clone can reproduce.

Call `_gitignore.ignored_untracked(root, paths)`. Three things it gets right that are each easy to
get wrong, with the measurements in `learnings/gitignore-anchoring-and-scope.md`:

- **The plain, index-consulting form**, so a manifest force-added inside an ignored directory still
  counts as one somebody maintains. Its sibling `ignored()` passes `--no-index` and asks about the
  *rules* — right for v2 and v3, wrong here.
- **Only a hide the repo carries.** `.git/info/exclude` is per-clone and the global excludes file is
  per-machine, and a path hidden by either returns exit 0 indistinguishably from one hidden by a
  committed `.gitignore`. Without that filter the walk answers about a *checkout* rather than a
  commit, so two machines derive different sets from one tree and a step recorded on the first can
  fail on the second.
- **The root is the work tree's own top level**, asserted before anything is asked. `check-ignore`
  run anywhere *under* a repo answers happily using that ancestor's rules, so a scratch copy inside a
  checkout that hides `tmp/` reports every file in it as hidden and the filter silently empties.

**Any exit outside `{0, 1}` means the question was never answered — stop, never proceed on the
unfiltered list.** Raise it out of the walk and catch it per command. `verify` owes **2**, the shape
having gone unobserved rather than observed and found wrong. `probe` owes **2** as well, printing the
question: a probe exiting 3 is a §4 stop, so it would end the whole walk and leave a repo git cannot
answer about with no route to `n/a` or `declined` for that version *or any after it* — measured on a
repo whose submodule held a `package.json`, where `check-ignore` aborts the batch with 128. `apply`
owes 3. Catch it rather than letting `_dispatch` turn it into a traceback, since `audit` records a
step against the first line of its output — and have `apply` ask the question *before* it writes
anything, so its catch can tell "nothing was written" from "this arose mid-run".

`selftest` holds this: any module under `steps/` that enumerates files must call `ignored_untracked`
or carry a comment containing `walk-unfiltered:` and the reason. Three details, each of which was
wrong in a first draft and is worth not rediscovering:

- **Match every enumerator, not `os.walk`.** `listdir`, `glob`, `rglob`, `scandir` and `iterdir`
  enumerate just as well, and `license-file-present.py` had been listing manifests with `listdir` in
  plain sight of a gate that reported nothing about it.
- **Match both call forms.** `from os import walk` and `from _gitignore import ignored_untracked` are
  ordinary, and an attribute-only test fails a correctly written step while passing a walking one.
  `ast.walk` is excluded by its receiver — it traverses syntax, not a filesystem.
- **The waiver must be a real comment**, found by `tokenize`. A substring test over the source is
  worse than no check: a docstring explaining why the filter matters quotes the marker, and the gate
  then prints `ok` for a module it never checked.

The waivers in the tree are worth reading before writing one — they are not boilerplate.
`memory-cache-symlink.py` lists a directory outside every repo; `memos-done-dated.py` reads a fixed
path v2 has already asserted is not ignored; `memos-directory.py` reads that path one step *before*
v2 does and says so; and `license-file-present.py` waives a defect it names rather than a case that
does not apply. **What the assertion proves is that the call is present, not that its result was
used** — a floor under the next author, not a substitute for reading the diff.

## `selftest` — the authoring gate

The gate is `python conventions.py selftest`. Run it before committing a new step, so the step is
exercised here rather than in the repos that will run it. It asserts:

- versions are unique and contiguous, every declared `script:` exists, and a step carrying fixtures has
  the script those fixtures exercise — a missing `<slug>.py` otherwise reads as "judgement only", which
  asks every repo a question and makes `applied` unrecordable for good;
- all five prose headings are present in every `<slug>.md`;
- every `probe` runs in a scratch copy and exits 0, 1 or 2 — never an uncaught traceback;
- per fixture: `verify` alone on an untouched `before/`, which must **fail**; then, where `probe` on that
  tree exits 0, `apply --dry-run`, `apply`, `verify`, and `apply` and `verify` **again** for idempotence;
  `verify` on `conformant/`, which must pass with the tree unchanged; and `apply` on every further
  fixture tree, which must refuse with exit 3 and write nothing;
- for a step carrying `supersedes:`, that the superseded step exists and carries its `## Superseded`
  section; for one carrying `retracted:`, that the named retracting version exists.

Whether the apply round trip is owed is read off `probe`, never off `apply`'s own exit code. A step
whose probe cannot return 0 is one `/adopt` never reaches apply on, and has nothing to assert there; a
step whose apply *crashes* on its own fixture used to report as the same thing, skipping the four
assertions that prove the migration works while the gate stayed green.

## Correcting a step that was wrong: `supersedes:`

A shipped step is never behaviourally edited. A repo already at v5 will never re-run v3, so an edit to v3
reaches only the repos that have not got there yet and leaves the rest in a state nothing will revisit.
Prose fixes are free; behaviour is not.

Write a **new** step carrying `supersedes: 3`, idempotent enough to repair both the unfixed state and the
mis-fixed one, and add a `## Superseded` section to step 3's prose pointing forward at its replacement;
`selftest` asserts both halves exist. The heading and the `retracted:` field below are different
mechanisms — one marks a step that was wrong, the other a convention the user reversed — so they are
deliberately not the same word, and a step may carry only one of them.

## Retracting a convention the user reversed: `retracted:`

A convention the user reverses is not a bug fix. Mark the original step with `retracted:` naming the
version that reverses it, and `/adopt` then skips it for any repo holding no line for it, recording
`n/a — retracted at v<n>` so contiguity still closes and the session-start notice stops nagging. A repo
that already applied it keeps its `applied` line, and the *retracting* step is what performs the undo.

## Retiring a step's script

A step's `.py` is permanent surface for a one-time migration, until it is not. Once every repo in the
fleet holds a terminal line for that version, delete the script: the `.md` keeps the prose and the
integer, and `audit` prints `NOT COVERED` for that line rather than a pass it can no longer justify. The
record, the engine and the hook are the parts that stay.
