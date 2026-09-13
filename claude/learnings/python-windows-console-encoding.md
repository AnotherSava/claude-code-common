# Python CLI output crashes on a non-UTF-8 Windows console

A Python CLI that prints arbitrary text — names, filenames, API data — will crash on Windows whenever
a character falls outside the console's active codepage, while the identical code is fine on macOS and
Linux. The machine's Windows locale decides the codepage; a Russian-locale machine gets **cp1251**, so
anything outside Cyrillic + Latin-1 kills the process:

```
  File "...\encodings\cp1251.py", line 19, in encode
    return codecs.charmap_encode(input, self.errors, encoding_table)[0]
UnicodeEncodeError: 'charmap' codec can't encode character '\xf4' in position 60794: character maps to <undefined>
```

The traceback points at the codec, not at the console, so it reads like corrupt data rather than an
output-encoding problem. Two tells that it is the console: the offending character is unremarkable
(`ô` here), and the same data round-trips fine through `json.dumps` or a file written with
`encoding="utf-8"`.

## Fix at the entry point

```python
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
```

`TextIOWrapper.reconfigure` exists in 3.7+. Do it once in the console-script entry point rather than
per-print, and don't reach for `errors="replace"` as the primary fix — that silently mangles the
characters instead of showing them. Modern Windows Terminal renders the UTF-8 bytes correctly; a
legacy console shows mojibake, which is still better than a crash.

`PYTHONIOENCODING=utf-8` fixes it too, but only for whoever remembers to set it — it doesn't travel
with the tool.

## Redirecting to a file does not make it safe

The trap is that the crash is usually *seen* on a console, so redirecting output to a log looks like
it sidesteps the problem. It doesn't: with a non-tty stdout Python falls back to
`locale.getpreferredencoding()`, which is the same cp1251 on the same machine. A background service
whose output goes to a log file is exposed exactly as much as an interactive run — and fails where
nobody is watching.

## `-X utf8` when you cannot edit the entry point

For launching *someone else's* script, or your own through a process manager, the UTF-8 mode flag is
the portable lever:

```
python -X utf8 serve.py
```

It is a plain argument, so it survives every launcher. An env-var prefix does not: a supervisor that
runs the command through `cmd.exe /c` on Windows has no shell that understands
`PYTHONIOENCODING=utf-8 python serve.py`, while the same string word-splits correctly under `nohup`
on Unix. One config value has to work on both — `-X utf8` does, the prefix does not.

`PYTHONUTF8=1` is the environment equivalent, with the same portability caveat.

## Reading is the opposite failure: it never raises

Everything above is about *writing*. Reading non-ASCII on the same machine fails in the mirror-image
way, and the difference matters because one of them is loud and the other is not. Measured 2026-09-13,
CPython 3.13.5, Russian-locale Windows.

Python opens stdio with **`errors="surrogateescape"`** — verified under bash, `cmd`, a direct
`subprocess` spawn, and with `-S`. So a byte the codepage cannot decode does not raise; it becomes a
lone surrogate. Feeding the UTF-8 bytes of `Привет 🎉` to a script's stdin:

```
PYTHONUTF8 unset:  encoding=cp1251  len=30  0x420 0x45f 0x421 0x402 0x420 0x451 …
PYTHONUTF8=1:      encoding=utf-8   len=21  0x41f 0x440 0x438 0x432 0x435 0x442 …
```

Twenty-one characters arrive as thirty. Nothing is raised and nothing is logged, and `json.load`
still succeeds on a payload like this because every structural character in JSON is ASCII — so a
program reading JSON off stdin runs to completion on silently corrupted *values*. cp1251 leaves
exactly one byte undefined (`0x98`, present in `И`, `'`, `😀`, `☑`), and even that surrogate-escapes
rather than raising.

The practical consequence is that a `try` around the read catches nothing, so "we handle bad input"
is false by construction: there is no bad-input path to take. Guard by **decoding explicitly**
(`sys.stdin.reconfigure(encoding="utf-8", errors="replace")` at the entry point, the input twin of
the fix above), not by catching.

Worth stating because the wrong mechanism is easy to write down confidently and is self-consistent:
a plausible chain of *"raises `UnicodeDecodeError` → a broad `except` swallows it → the program runs
on an empty payload"* predicts an empty payload, and what you actually get is a full one that is
wrong. Diagnosing from the first story means looking for an exception that was never thrown.

## Turning it on changes more than output

`PYTHONUTF8=1` is a **process-wide interpreter mode**, not a stdio setting, and it reaches three
things beyond the streams — the default encoding of every `open()` with no explicit `encoding=`,
`locale.getpreferredencoding()`, and how `subprocess` decodes a child under `text=True`. Two of those
can turn a silent wrong answer into a failure, which is usually what you want, and one of them
produces a failure nobody can catch:

```python
subprocess.run(["cmd", "/c", "echo Привет"], capture_output=True, text=True)
# PYTHONUTF8 unset:  rc=0  stdout='ЏаЁўҐв\n'     wrong glyphs, no error
# PYTHONUTF8=1:      rc=0  stdout=None
#   Exception in thread Thread-1 (_readerthread): UnicodeDecodeError … byte 0x8f
```

The decode happens on `subprocess`'s own reader thread, so the exception reaches stderr and never
reaches the caller: `returncode` is `0` and `stdout` is `None`. A caller that does
`result.stdout.strip()` inside a `try/except subprocess.SubprocessError` fails later, elsewhere, with
`AttributeError`. Identical for `powershell -NoProfile -Command`.

The reason a child trips this at all is that **a Windows box has two codepages and they differ**: the
ANSI codepage governs Python's stream decoding (`cp1251` here) while console programs write the OEM
codepage (`chcp` → `866` on the same machine). Neither is UTF-8, so forcing UTF-8 mode fixes the ones
that produce UTF-8 and breaks the ones that do not. Pass `encoding=` explicitly on any
`subprocess.run` whose child is a console program, rather than relying on the process default:

```python
subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
```

Also worth knowing when the variable is set by a launcher rather than by the user's shell — a config
file, a service manager, an agent harness. The same script then behaves differently under the
launcher than it does when the user runs it by hand, and a cp1251 CSV that opens fine in their
terminal raises `UnicodeDecodeError` under the tool. `env | grep PYTHONUTF8` in the ambient shell is
the check.

## Worth catching before shipping

Non-ASCII output is easy to miss in testing when the fixtures are ASCII. Unit tests over canned
payloads won't reach it either, since they assert on returned values rather than on `print`. The
cheapest guard is to run the real command once against real data on Windows; it fails immediately and
loudly on the first offending record.
