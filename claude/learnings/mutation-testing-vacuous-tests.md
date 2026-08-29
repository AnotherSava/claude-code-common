# Mutation testing, and the two ways it quietly lies

Mutation testing is the only cheap check that a test asserts anything: break the code deliberately, and
if the suite stays green the test was decoration. It works — but the run itself has two failure modes
that both present as "all mutants killed", and both were measured on 2026-08-27 while adding five cases
to a repo that leans on this technique heavily.

## 1. A fixture already in the mutant's output form makes the test vacuous

The command under test printed a JSON file verbatim, deliberately: its caller compares the *deployed*
artefact byte-for-byte against the *committed* one, so re-serialising would erase the difference the
comparison exists to find.

```python
sys.stdout.write(raw)                        # correct
sys.stdout.write(json.dumps(json.loads(raw)))  # the mutant
```

The test read the fixture off disk and asserted stdout equalled it. It passed on **both**. The fixture
was written by the test harness as `json.dumps({...})` — so it was *already* in exactly the form a round
trip returns, and the two implementations were byte-identical against it.

The fix is one line, and it belongs in the test rather than the fixture (other cases depend on the
fixture's shape):

```python
with open(path, encoding="utf-8") as fh:
    pretty = json.dumps(json.load(fh), indent=2) + "\n"   # a form a round trip does NOT reproduce
box.write(path, pretty)
```

**The general rule: an "X is preserved" test is only meaningful if the fixture is in a state the wrong
implementation would visibly change.** Canonical, normalised, minimal, already-sorted, already-trimmed —
any fixture that happens to be a fixed point of the transformation you are trying to forbid asserts
nothing. Ask what the mutant would output, and if the answer is "the same bytes", the fixture is wrong.

Same shape elsewhere: asserting a sorter is stable using an already-sorted list; asserting whitespace is
preserved using input that has none; asserting a formatter is idempotent starting from its own output.

## 2. A refusal test that passes because the operation would have failed anyway

The second case guarded against a path escaping its parent directory — a host name read off disk being
joined into `hosts/<name>/manifest.json`, where a `name` of `..` reaches one level up.

```python
for name in ("..", "../..", "../../etc"):
    r = run(LANDLORD_HOST=name)
    assert r.code == 2 and not r.stdout
```

Deleting the guard entirely did not fail this. Without it the traversal resolved to
`hosts/../manifest.json`, **which did not exist**, so the command exited 2 for a completely different
reason and the assertion held. The test proved only that a nonexistent path is an error.

The fix is to plant what makes refusal distinguishable from failure:

```python
# Real, readable and VALID one level up, so an unguarded implementation answers `..` with exit 0.
box.write(os.path.join(box.repo, "identity-manifest.json"), json.dumps({...}))
```

**A test for a refusal must make the refused operation otherwise SUCCEED.** If the thing you are
forbidding would fail on its own, you are testing the failure, not the guard. Applies to authorization
checks against resources that do not exist, rate limits below the natural throughput, and validation
rejecting input that would have crashed the parser regardless.

Fixing this one exposed a real hole in the code it was written for: the guard had been placed in the
file-reading branch only, so the environment-variable branch returned early and bypassed it. That is the
payoff — a vacuous test hides the bug it was written to catch, in the code you wrote minutes ago.

## 3. A fixture whose only violation is out of the component's scope

The subtlest of the three, and the one that survives review because the test looks adversarial. Two
linters were being compared — a strict one with the full context, and a weaker one deliberately given
less. The fixture was a config file carrying a hostname the tenant had not been granted:

```
landlord:      FLAGS — "site address `vancouverprintlab.ca` is not granted to this tenant"
ingress-lint:  clean
```

Read as a gap, and it nearly went out as a bug report. It was not one. The only violation in the fixture
was a *grant* violation, and the second linter is called with no grant list precisely because it runs on
a workstation that cannot know one. It returned clean **for the right reason**. The test could not tell
"correctly out of scope" from "failed to detect", which are opposite verdicts.

The fix is to pick a violation the component under test is in scope to catch. Here that meant a rule
needing nothing but the file — swapping the ungranted hostname for a port-only address — plus a control
with the same violation and none of the construct being tested:

```
CONTROL: port-only, no heredoc      landlord: FLAGS   other: FLAGS   <- fixture is meaningful
port-only AFTER a heredoc brace     landlord: FLAGS   other: FLAGS   <- and the construct is handled
```

**This confusion is not test-only, and the production version costs more.** The same linter's own applicability
gate later turned out to make it: it folded "this repo declares a different file" together with "this repo
declares nothing" into one silent skip, so a live tenant vhost on a checkout missing its config printed
`clean (2 file(s) checked)` — character-for-character what a real pass prints. A fixture that cannot separate
"correctly out of scope" from "failed to detect" wastes a test; a *gate* that cannot separate them ships the
verdict. Whenever this section's distinction shows up in a test, check whether the code under test draws it
either. `cross-repo-rule-delegation.md` has the fix.

Without the control the first line is unverified, and a fixture that flags for an unrelated reason looks
identical to one that works.

**When comparing two implementations, the fixture must contain a violation BOTH are in scope to detect.**
Otherwise the comparison measures the scope difference you already knew about. Generalises past linters:
any test asserting parity between a full and a reduced configuration — a feature-flagged path, a free
versus paid tier, an offline versus online client — needs its assertion aimed at behaviour both share.

## 4. Filtering the run's output so that "survived" looks like "killed"

A mutation run prints one line per case. Filtering it to keep the run readable:

```bash
python3 tests/commands.py | grep -E '^  (ok|FAIL) manifest'
```

The harness printed `  FAIL manifest …` with one space and `  ok   manifest …` with three, so that pattern
matched failures and never successes. Then:

```bash
run | grep -i 'byte-for-byte'      # no output
```

No output was read as "no failure", i.e. mutant killed. It actually meant the opposite — the mutant
survived and printed an `ok` line the filter could not match. Two of four mutants were scored as kills
this way, and only re-reading the pattern against the harness's exact spacing caught it.

**Print the baseline through the same filter before trusting a single result.** If the filtered baseline
is empty when everything passes, the filter cannot distinguish pass from fail and every "kill" it reports
is unfounded. Cheaper still: match on the case name and show whatever status comes with it, rather than
enumerating the statuses you expect.

This is the testing-side instance of a rule that also applies to linters and type-checkers: grepping a
checker's output for "the errors I care about" discards both the exit code and the error sitting beside
the one you filtered for.

## Running the mutations at all

Two mechanical prerequisites, both of which have silently invalidated whole runs:

- **Clear `__pycache__` between mutations.** CPython validates cached bytecode on source mtime *and
  size*, so a same-length edit — `0`→`1`, `>`→`<`, `hours=24`→`hours=48` — leaves a `.pyc` it happily
  reuses. Same-length edits are the most common mutations there are. `PYTHONDONTWRITEBYTECODE` stops
  bytecode being *written*, never *read*, so it is not sufficient on its own. See
  `python-stale-bytecode-cache.md`.
- **Assert the mutation applied.** Patch with a script that fails loudly when the target string is
  absent, rather than a `replace()` that silently no-ops after the source is reworded:

  ```python
  s = open(p).read()
  assert TARGET in s          # a survived mutant and an unapplied one look identical without this
  open(p, 'w').write(s.replace(TARGET, MUTANT))
  ```

  Keep a pristine copy (`cp file /tmp/file.bak`) and restore from it rather than reversing the edit —
  an inverse `replace()` fails the same silent way.
