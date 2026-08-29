# Delegating to rules that live in another repo

The "one copy of the logic" rule is easy inside a codebase and gets abandoned at a repo boundary, because
importing across it is awkward and copying is not. The copy then drifts silently — and a drifted *checker* is
worse than a drifted feature, because its output is the thing you would otherwise use to catch the drift.

Measured case: a workstation lint reimplemented four rules whose authoritative copy lived in the repo that
enforces them on the box. The rules were transcribed correctly; the *reader* feeding them was weaker than the
original's, so three ordinary constructs reached no rule at all and the lint printed `clean`. It had been
reporting clean on hijack-capable configs for as long as it had existed, and nothing disagreed with it, because
the only other opinion was in a repo it never called.

## Load the other repo's module by path

No packaging, no vendoring, no submodule:

```python
spec = importlib.util.spec_from_file_location("vhost_lint", os.path.join(landlord, "bin", "vhost-lint.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
return module.lint(path, None, None)
```

Three things make this hold up, and each of them is the answer to a way it silently fails:

**Find the repo by env var, then by convention — and validate the file, not the directory.**

```python
candidates = [os.environ.get("CLAUDE_LANDLORD"), os.path.join(os.path.dirname(repo_root), "landlord")]
for candidate in candidates:
    if candidate and os.path.isfile(os.path.join(candidate, "bin", "vhost-lint.py")):
        return candidate
```

Checking `isdir(candidate)` instead is the bug: a stale variable pointing at a moved or half-deleted checkout
passes, and the failure resurfaces later as an import error from inside a `try` that swallows it. Testing for
the file being imported means a stale variable falls through to the convention path.

**Gate on applicability, or the borrowed rules become false positives.** Rules written for one context describe
that context only. These described a vhost installed into a shared `conf.d`; applied to an ordinary standalone
Caddyfile they flagged three constructs — a keyless global-options block, a snippet definition, a port-only
address — that are all legitimate when you own the proxy. The gate has to be a fact already recorded somewhere,
not a guess: here, whether the file is the one `VHOST_SRC` in `config/publish.env` names.

**But that gate has three answers, not two.** Its first coding was `if not vhost_src: return [], []`, which
folded "this repo names a different file" together with "this repo names nothing" and skipped both in silence.
Only the first is a decision. The second is the absent-dependency case below wearing different clothes, and it
arrived at the same place: a checkout of a live tenant whose `config/publish.env` had not yet reached it printed
`clean (2 file(s) checked)` over the vhost that repo's own commit gate calls this script to check, having
applied no tenancy rule to it — the same sentence, to the character, that a real pass prints. Making the
*dependency*'s absence loud while leaving the *declaration*'s absence silent closes one door and leaves the
other one open.

Split them, and give the repo a way to say the quiet thing on purpose:

| `VHOST_SRC` | what the repo has said | outcome |
| --- | --- | --- |
| names this file | the rules describe it | run them |
| names another file | answered, and not this one | silence |
| present but empty | "this repo installs no vhost" | silence |
| absent | nothing | **NOT CHECKED** |
| names a file that is not there | answered with a path that is gone | **NOT CHECKED**, once per repo |

That last row is the easiest one to leave out and it is the same bug a third time: every file is skipped for not
being the declared one, so a declaration left pointing at a moved path makes the whole rule set apply to nothing
while each individual skip still looks correct. Report it per *repo*, not per file — the fault is in the
declaration, and the skipped files are only its symptom.

The general shape: an applicability gate that reads a config value must distinguish *configured otherwise* from
*not configured*, and only the first may be quiet. For any silent skip, ask what the operator would have had to
do for that silence to be their decision. If the answer is "nothing", it is not one.

**Read that config line-wise; do not source it.** `config/publish.env` looks like shell and mostly is, but one
value was a semicolon-separated *program* — sourcing it to read one key would have run `ssh`.

## The absent-dependency case is a third outcome, not an error and not silence

If the other repo is not checked out there are no rules to run, and both obvious codings are wrong: raising
breaks the tool for everyone who does not have the dependency, and skipping quietly means a fresh machine
reports `clean` on a file nothing examined. Neither is what happened, so neither should be printed.

Give the function a third return channel that does not touch the exit status:

```python
def lint(paths) -> tuple[list[str], int, list[str]]:   # (problems, files scanned, notices)
```

and make the summary line refuse to say the reassuring word while a notice is outstanding:

```
ingress-lint: no violations in what ran, but 1 check(s) above did NOT run (1 file(s) seen)
```

Exit 0 either way — a missing optional dependency is not a violation — but the two exit-0 sentences are not
interchangeable. Every caller has to carry the channel too, or it dies one level up: the hook feeding this to a
model puts notices in `additionalContext` *even when there are no violations*, since a silent hook is exactly
how "could not check" becomes "checked, fine".

## Test the delegation, not the rules

The other repo tests its own rules; duplicating those cases here would recreate the drift in the test suite.
What is worth pinning locally is everything this side owns: that the rules get called for the right file, that
they are skipped for the wrong one, and that each of the three ways they can fail to run — absent checkout,
absent declaration, declaration pointing at nothing — produces a notice rather than silence. Write the
silent cases and the notice cases next to each other in the test file; a row of the table above missing from it
is exactly how one of them goes back to being quiet.

Stub the dependency so the tests run on a machine that lacks it — and have the stub assert the arguments it
received, which is the part a real dependency would accept without comment:

```python
def lint(path, owns, capabilities):
    if owns is not None or capabilities is not None:
        return [f"{path}:0: STUB — expected None/None, got {owns!r}/{capabilities!r}"]
    return [f"{path}:1: STUB VERDICT"]
```

That distinction matters here beyond argument-checking: `None` meant "skip the rules needing host data" while
an empty `set()` meant "this host grants nothing", so passing `set()` would have fired a rule on every
legitimate import. A stub returning a fixed verdict cannot tell you the construct was *detected*, only that the
call happened — so verify detection separately, once, against the real dependency, and say in the test file
which of the two each case proves.
