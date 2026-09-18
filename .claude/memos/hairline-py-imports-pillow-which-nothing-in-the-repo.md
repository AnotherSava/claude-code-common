---
created: 2026-09-13 11:21:32
---

# hairline.py imports Pillow, which nothing in the repo declares

`claude/skills/docs-relevance/scripts/hairline.py` does `from PIL import Image, ImageChops`, unguarded. That is the first third-party Python import in this repo's own tree, and nothing records it: README's installation section covers symlinks and a bare `python` on PATH, and says nothing about Pillow. Flagged 2026-09-13 by the Windows session, which had Pillow only by accident of unrelated work.

Anything calling that script on a machine without Pillow fails at import with a traceback, and the capture scripts on both platforms call it unconditionally.

Two things to settle, neither obvious enough to guess at:

- **Where the dependency is declared.** This repo has no `requirements.txt`, no `pyproject.toml`, and deliberately keeps the hooks stdlib-only so `python -S` can run them. A capture script is not a hook and may reasonably depend on more, but the boundary should be written down rather than inferred from which files happen to import what.
- **How it gets installed**, and whether a missing Pillow should be a clear message naming the install command rather than an ImportError traceback.

Also reported in the same review: the script's no-argument path prints a mid-sentence fragment instead of a usage synopsis, on macOS as well. Small, and worth fixing in the same pass.
