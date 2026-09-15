---
created: 2026-09-13 11:21:32
platform: windows
---

# PYTHONUTF8 changes subprocess decoding, and the failure is invisible

**The shape to hold on to: `returncode` 0, `stdout` `None`, and the exception raised on a thread the caller cannot catch.** This is not a wrong-string bug, which is how the title reads and how it will be misremembered. `subprocess.run(..., text=True)` decodes in its own reader thread, so when that decode raises, the call still returns — successfully, by every signal the caller can test. The traceback goes to stderr where nothing reads it, the caller's own `try`/`except` never fires, and the program dies later and elsewhere with `AttributeError` on the `None`. A reader on macOS will never picture this, because there the decode simply succeeds.

`PYTHONUTF8=1` was added to `claude/settings.json`'s `env` block to stop Windows mangling hook payloads. It is process-wide rather than hook-scoped, so it also changes the default encoding of every bare `open()` and of `subprocess.run(..., text=True)` in any Python that Claude Code spawns.

Reported 2026-09-13 by the session on the Windows box, measured there and not reproducible on macOS. Console output on that machine is codepage 866. Without the variable, a subprocess's output decodes as the ANSI codepage — wrong glyphs, no error. With it, it takes the path above.

Reproduced there against the `git()` helper in `github-status/scripts/repos-status.py`, on a commit whose message carries non-ASCII.

Worth doing: audit the repo's own scripts for `subprocess.run(..., text=True)` where the child's output is not UTF-8, and decide between passing an explicit `encoding=`/`errors=` at those call sites or capturing bytes and decoding deliberately. The variable itself should stay — it fixes real breakage documented in README's "UTF-8 mode" section. This is about the blast radius it came with, which was not priced at the time.
