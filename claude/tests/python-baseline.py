#!/usr/bin/env python3
"""Every Python file in this repo loads on the oldest interpreter a caller can hand it.

That floor is macOS's system Python, 3.9. Nothing is pinned to it — the same machine runs Homebrew
3.14 interactively — but a non-interactive `ssh` session resolves `python3` to `/usr/bin/python3`,
and two things arrive that way: the `github-status` peer scan, which pipes its script into the far
machine's interpreter, and any repo whose commit gate runs `python3 claude/conventions/check.py .`
under whatever `python3` the caller happens to have.

Measured, 2026-09-16: nine files under `claude/conventions/` annotated with
`tuple[int, int, str] | None`, which 3.9 evaluates at def time and refuses. The peer scan reported
`conventions unmeasured` for fifteen repos on the other machine, every convention command was
unrunnable there, and each of those files was correct on 3.10 and up — while the scan's own script,
two directories away, already carried the one import that fixes them.

What is asserted, per file:

  grammar        it parses under the 3.9 grammar, so syntax that interpreter cannot read is refused
                 here rather than on the machine that cannot read it
  annotations    a PEP 604 union in an annotation position requires `from __future__ import
                 annotations`, which defers the evaluation that fails

What this cannot see: a union outside an annotation — `Alias = int | None`, `isinstance(x, int |
str)` — is a runtime expression no import defers. Those are invisible here and fail on the floor at
the moment the line runs.

Usage:  python claude/tests/python-baseline.py
Exit:   0 every file loads on the floor, 1 one does not or could not be read
"""

from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# Raise this only when no caller can hand the repo an older interpreter — which today means when
# macOS stops shipping 3.9 as /usr/bin/python3, not when this machine upgrades.
FLOOR = (3, 9)

# Directories carrying code nobody here maintains, or no code at all.
SKIPPED = {".git", ".venv", "node_modules", "__pycache__", "tmp", "venv"}

FUTURE_IMPORT = "from __future__ import annotations"

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def sources() -> list[str]:
    """Every .py file under the repo, repo-relative, forward slashes."""
    found: list[str] = []
    for directory, subdirectories, names in os.walk(REPO):
        subdirectories[:] = [name for name in subdirectories if name not in SKIPPED]
        for name in names:
            if name.endswith(".py"):
                found.append(os.path.relpath(os.path.join(directory, name), REPO).replace("\\", "/"))
    return sorted(found)


def annotation_unions(tree: ast.AST) -> bool:
    """True when some annotation is a PEP 604 union, which the floor evaluates rather than defers."""
    annotations: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        elif isinstance(node, ast.arg) and node.annotation is not None:
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            annotations.append(node.returns)
    return any(isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr)
               for annotation in annotations for inner in ast.walk(annotation))


def check(relative: str) -> None:
    path = os.path.join(REPO, relative)
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"{relative}: could not be read ({exc})")
        return
    try:
        tree = ast.parse(text, filename=relative, feature_version=FLOOR)
    except SyntaxError as exc:
        floor = ".".join(str(part) for part in FLOOR)
        fail(f"{relative}: does not parse under Python {floor} ({exc.msg}, line {exc.lineno})")
        return
    if annotation_unions(tree) and FUTURE_IMPORT not in text:
        fail(f"{relative}: annotates with `X | Y` and does not carry `{FUTURE_IMPORT}`, so importing "
             f"it raises TypeError on the floor")


def main() -> int:
    files = sources()
    if not files:
        # Nothing compared is not the same answer as nothing wrong, and must not print like it.
        print(f"python baseline: NOT CHECKED — no .py files found under {REPO}")
        return 1
    for relative in files:
        check(relative)
    if FAILURES:
        print(f"python baseline: {len(FAILURES)} file(s) will not load on Python "
              f"{'.'.join(str(part) for part in FLOOR)}\n")
        for failure in FAILURES:
            print(f"  {failure}")
        print()
        return 1
    print(f"python baseline: {len(files)} file(s) load on Python "
          f"{'.'.join(str(part) for part in FLOOR)} — runtime unions outside annotations unchecked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
