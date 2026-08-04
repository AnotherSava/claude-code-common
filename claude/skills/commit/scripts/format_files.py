#!/usr/bin/env python3
"""Align a commit plan's file list into two columns.

Rendered markdown collapses runs of spaces, so a hand-padded list only lines up
inside a fenced code block. This reads the pairs and emits that block ready to
paste verbatim into the commit plan.

Usage:
    python3 format_files.py <<'EOF'
    src/background.ts	Render/push, consumer gating
    manifest.json	Expose card faces to BGA pages
    EOF

Input is one `path<TAB>description` pair per line on stdin. Blank lines are
skipped. A line with no tab is treated as a path with no description. Paths are
padded to the longest one so descriptions form a column; nothing is truncated,
since a clipped path is worse than a wide block.

Options:
    --no-fence   Emit the aligned lines without the surrounding ``` fence.
    --gap N      Spaces between the columns (default 3).
"""

import argparse
import sys


def format_rows(rows: list[tuple[str, str]], gap: int) -> list[str]:
    """Pad each path to the longest, so descriptions align into a column."""
    width = max((len(path) for path, _ in rows), default=0)
    lines = []
    for path, description in rows:
        lines.append(f"{path.ljust(width)}{' ' * gap}{description}".rstrip())
    return lines


def parse_rows(text: str) -> list[tuple[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        path, _, description = line.partition("\t")
        rows.append((path.strip(), description.strip()))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-fence", action="store_true", help="omit the surrounding code fence")
    parser.add_argument("--gap", type=int, default=3, help="spaces between columns (default: 3)")
    args = parser.parse_args()

    rows = parse_rows(sys.stdin.read())
    if not rows:
        print("format_files.py: no input rows", file=sys.stderr)
        return 1

    lines = format_rows(rows, args.gap)
    if not args.no_fence:
        lines = ["```"] + lines + ["```"]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
