#!/usr/bin/env python3
"""Decide whether the pending change set needs /clean-code and /docs-relevance.

Prints one verdict line per sub-skill, `RUN` or `SKIP`, with the reason and the
paths behind it. A change set git cannot be read from prints `RUN` for both and
says the scope is unmeasured — a gate that could not look must never skip.
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared"))
from git_changeset import changed_paths, git  # noqa: E402  (the shared module's path is set above)

CODE_SUFFIXES = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".go", ".java", ".kt",
    ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh",
    ".ps1", ".psm1", ".sql", ".css", ".scss", ".sass", ".html", ".svelte", ".vue", ".lua",
    ".json", ".toml", ".yml", ".yaml", ".gradle", ".cmake", ".m", ".mm", ".dart", ".ex", ".exs",
}
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".adoc"}

# Paths whose content documents nothing about the code and is never read for staleness.
INERT_PREFIXES = (".claude/memos/", ".claude/memory/")
INERT_PATHS = {".claude/conventions"}


def unpushed_paths() -> tuple[list[str], str | None]:
    """Paths touched by commits not yet on the remote, and a note when that cannot be determined.

    What has not reached the remote is unreviewed whether or not it is still in the tree, so the
    gate reads both. Where there is no upstream the range is every commit, which this script has
    no basis to bound — it says so rather than reporting the working tree as the whole scope.
    """
    try:
        git(["rev-parse", "--abbrev-ref", "@{upstream}"])
    except subprocess.CalledProcessError:
        return [], "no upstream, so unpushed commits are unmeasured here — see /commit step 1"
    raw = git(["diff", "--name-only", "-z", "--diff-filter=ACMRT", "@{upstream}..HEAD"], binary=True)
    return [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p], None


def suffix_of(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return ("." + base.rsplit(".", 1)[1].lower()) if "." in base else ""


def is_code(path: str) -> bool:
    """A known code suffix, or an extensionless file whose first line is a shebang.

    Git hooks and shell utilities carry no suffix, so suffix matching alone files them as
    neither code nor documentation — and a change touching only `git/hooks/pre-push` would
    then skip the sub-skill that exists to review it.
    """
    if suffix_of(path) in CODE_SUFFIXES:
        return True
    if suffix_of(path):
        return False
    try:
        with open(path, "rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def classify(paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    code, docs, inert = [], [], []
    for path in paths:
        if path in INERT_PATHS or path.startswith(INERT_PREFIXES):
            inert.append(path)
        elif is_code(path):
            code.append(path)
        elif suffix_of(path) in DOC_SUFFIXES or path.startswith("docs/"):
            docs.append(path)
        else:
            inert.append(path)
    return code, docs, inert


def sample(paths: list[str], limit: int = 4) -> str:
    shown = ", ".join(paths[:limit])
    return f"{shown}, +{len(paths) - limit} more" if len(paths) > limit else shown


def main() -> None:
    try:
        tree = changed_paths()
        unpushed, note = unpushed_paths()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"scope: UNMEASURED — git failed ({exc}); both sub-skills MUST run")
        print("clean-code: RUN (scope unmeasured)")
        print("docs-relevance: RUN (scope unmeasured)")
        return

    paths = sorted(set(tree) | set(unpushed))
    if note:
        print(f"scope: {note}")
    if not paths:
        print("scope: nothing uncommitted and nothing unpushed")
        print("clean-code: SKIP (nothing changed)")
        print("docs-relevance: SKIP (nothing changed)")
        return

    code, docs, inert = classify(paths)
    print(f"scope: {len(paths)} path(s) — {len(tree)} uncommitted, {len(unpushed)} in unpushed commit(s) — "
          f"{len(code)} code, {len(docs)} doc, {len(inert)} neither")
    only_unpushed = sorted(set(unpushed) - set(tree))
    if only_unpushed:
        print(f"  committed but unpushed, so reviewed by this run too: {sample(only_unpushed)}")
    if code:
        print(f"  code: {sample(code)}")
    if docs:
        print(f"  doc:  {sample(docs)}")
    if inert:
        print(f"  else: {sample(inert)}")

    if code:
        print(f"clean-code: RUN ({len(code)} code file(s) changed)")
    else:
        print("clean-code: SKIP (no file with a code suffix changed)")

    if code or docs:
        reason = "code changed, so prose about it may be stale" if code else "documentation itself changed"
        print(f"docs-relevance: RUN ({reason})")
    else:
        print("docs-relevance: SKIP (no code and no documentation in the change set)")


if __name__ == "__main__":
    main()
