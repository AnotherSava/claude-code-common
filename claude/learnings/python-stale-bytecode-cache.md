# A stale `__pycache__` can make a test run report on code that no longer exists

Found while mutation-testing a Python test suite: the suite passed on a mutation it was written to reject,
and insisted a constant was `25` while the file plainly said `30`. Not a flaky test — the harness was
importing bytecode compiled from an earlier version of the source, and reporting on it with complete
confidence.

## Why it happens, and why mutation testing hits it hardest

By default CPython validates a cached `.pyc` against the source's **mtime and size** (PEP 552 calls this
timestamp invalidation). Both must match the header for the cache to be reused. So the cache goes stale
exactly when an edit changes **neither**:

- **The size is unchanged.** `hours=24` → `hours=30` → `hours=48`; `VALUE = 11` → `VALUE = 99`;
  `>=` → `<=`; `True` → `_ALL` . Same-length edits are the *commonest* kind of mutation, which is why a
  mutation-testing loop is the thing most likely to trip over this.
- **The mtime is unchanged**, either because the write fell inside the filesystem's timestamp
  granularity, or because something restored it — a `tar`/`rsync` that preserves times, a checkout, or a
  script that rewrites a file and puts the timestamp back.

The failure is silent and confident: the suite runs, passes, and reports on a module that does not match
what is on disk. In a mutation run that inverts the result you care about — a surviving mutant looks like a
gap in your tests, when in fact your mutation was never loaded.

## The fix that is only half a fix

`PYTHONDONTWRITEBYTECODE=1` (or `python -B`) **does not help on its own.** It stops bytecode being
*written*; it does not stop an existing stale `.pyc` from being *read*. Measured:

```bash
$ python3 -c "import mod; print(mod.VALUE)"          # 11, and writes __pycache__
# same-length edit to VALUE = 99, with os.utime() restoring the original mtime
$ PYTHONDONTWRITEBYTECODE=1 python3 -c "import mod; print(mod.VALUE)"
11        # ← the flag alone still reads the stale cache
$ rm -rf __pycache__ && python3 -c "import mod; print(mod.VALUE)"
99
```

That makes it worse than useless in a test runner: it *looks* like a guard while changing nothing on the
one run where it matters.

**Do both, in this order:** remove `__pycache__` first — that is the load-bearing half — then set the flag
so nothing is left behind for the next run to trip on. Put it in the runner rather than in a README; a
guard that has to be remembered is not a guard.

```bash
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
export PYTHONDONTWRITEBYTECODE=1
```

## Reproducing it on demand — the part that trips people first

A naive attempt reproduces nothing, and you conclude the bug is not real: an ordinary editor write bumps
the mtime, so the cache correctly invalidates. To force the actual condition, restore the mtime after a
same-length edit so both fields match the header:

```python
import os
st = os.stat(path)
open(path, "w").write(mutated_source)          # same length as the original
os.utime(path, (st.st_atime, st.st_mtime))     # put the timestamp back
```

Then the same source read directly reports a pass, and read through a cache-clearing runner reports the
failure it should — the harness lying, on demand, and then the guard defeating it.

## Two things that make it harder to spot

- **Scripts without a `.py` extension** — a `bin/` entry point imported by tests — produce cache files
  whose names do not obviously correspond to anything, so a stale one is not caught by eye.
- **A same-length edit leaves the file size identical**, so the usual "did my change land?" instinct of
  checking a byte count confirms the wrong thing.

## The principled alternative

Hash-based `.pyc` files (PEP 552) validate against a hash of the source rather than its timestamp, and are
immune to all of this. They are not the default, but they are available where you control compilation:

```bash
python3 -m py_compile --invalidation-mode checked-hash <file>
```

Worth knowing for a build that produces bytecode deliberately; for a test runner, clearing the cache is
simpler and needs no cooperation from whoever runs it.
