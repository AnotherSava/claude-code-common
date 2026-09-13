---
created: 2026-09-13 11:21:32
---

# PYTHONUTF8 changes subprocess decoding, and the failure is invisible

`PYTHONUTF8=1` was added to `claude/settings.json`'s `env` block to stop Windows mangling hook payloads. It is process-wide rather than hook-scoped, so it also changes the default encoding of every bare `open()` and of `subprocess.run(..., text=True)` in any Python that Claude Code spawns.

Reported 2026-09-13 by the session on the Windows box, measured there and not reproducible on macOS. Console output on that machine is codepage 866. Without the variable, a subprocess's output decodes as the ANSI codepage — wrong glyphs, no error. With it, the decode raises *inside subprocess's reader thread*, which is the bad part: `returncode` stays 0, `stdout` comes back `None`, the traceback goes to stderr where nothing reads it, and the caller's own try/except never sees anything. It then fails later and elsewhere with `AttributeError` on the `None`.

Reproduced there against the `git()` helper in `github-status/scripts/repos-status.py`, on a commit whose message carries non-ASCII.

Worth doing: audit the repo's own scripts for `subprocess.run(..., text=True)` where the child's output is not UTF-8, and decide between passing an explicit `encoding=`/`errors=` at those call sites or capturing bytes and decoding deliberately. The variable itself should stay — it fixes real breakage documented in README's "UTF-8 mode" section. This is about the blast radius it came with, which was not priced at the time.
