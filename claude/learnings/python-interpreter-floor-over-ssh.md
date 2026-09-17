# The Python a caller hands you, and the syntax that survives it

A script run over a non-interactive `ssh` does not get the interpreter that machine uses. Measured
2026-09-16 on a macOS box:

```
ssh <host> 'python3 -V'                      -> Python 3.9.6      /usr/bin/python3
ssh <host> 'zsh -lic "python3 -V"'           -> Python 3.14.7     /opt/homebrew/bin/python3
```

A non-interactive shell reads no login profile, so `/opt/homebrew/bin` is not on `PATH` and
`python3` falls through to the system copy macOS still ships. Anything piped into a peer — a status
scan, a remote check, a one-off probe — is therefore running on 3.9 while every interactive session
on that same machine runs something years newer.

The same asymmetry reaches a commit gate: a `python3 <script>` line in a hook or a gate resolves to
whatever `python3` that caller happens to have, and nothing in the repo says which one that is.

## PEP 604 is a runtime failure, not a syntax error

```python
def behind_for(root: str) -> tuple[int, int, str] | None: ...
```

On 3.9 this **parses** and then raises when the `def` executes:

```
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
```

Annotations are evaluated eagerly, so the union is built at definition time. Two consequences:

- `python -m py_compile` and any syntax-only check pass it. Only an import reveals it.
- The error surfaces at *import*, so a module that is merely loaded — a rule, a plugin, a helper —
  takes its whole caller down with a message about `|` that names no version at all.

The fix is one line, first statement after the module docstring:

```python
from __future__ import annotations
```

That turns every annotation into a string and defers evaluation, so the union is never built.

**What it does not fix:** a union outside an annotation position is an ordinary runtime expression
and no import defers it.

```python
Alias = int | None                 # still TypeError on 3.9
isinstance(x, int | str)           # still TypeError on 3.9
```

Those have to be written `Optional[int]` / `(int, str)` to reach the floor.

## Asserting the floor statically

Two checks catch everything the future import can help with, and they run on any interpreter:

```python
import ast

FLOOR = (3, 9)

# Grammar: a `match` statement, and anything else newer than the floor, raises SyntaxError here
# even though the running interpreter parses it happily.
tree = ast.parse(source, feature_version=FLOOR)

# PEP 604 in annotation position: walk only the annotations, then look for BinOp/BitOr inside them.
spots = []
for node in ast.walk(tree):
    if isinstance(node, ast.AnnAssign):
        spots.append(node.annotation)
    elif isinstance(node, ast.arg) and node.annotation is not None:
        spots.append(node.annotation)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
        spots.append(node.returns)
found = any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)
            for spot in spots for n in ast.walk(spot))
```

A grep is not a substitute. `] | None`, `str | None` and friends each miss the others — one such
sweep found nine files and left a tenth (`Path | None`) that failed the moment the gate ran.

## Testing a fix on the peer without touching its checkout

Ship the tree to a temp directory over the same ssh, run there, delete:

```bash
tar -cz -C /path/to/repo . | ssh host 'set -e; d=$(mktemp -d); tar -xz -C "$d"; cd "$d";
  python3 <the thing>; rm -rf "$d"'
```

This proves the change under the peer's real interpreter while its own working tree stays
untouched — which matters when a session over there is mid-edit.

One limit to expect: anything that compares against an *installed* path will report every link as
wrong, because the temp copy is not the checkout those links point at. Use it for "does this
import / parse / run", not for "does this machine's install agree with this tree".
