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

## Worth catching before shipping

Non-ASCII output is easy to miss in testing when the fixtures are ASCII. Unit tests over canned
payloads won't reach it either, since they assert on returned values rather than on `print`. The
cheapest guard is to run the real command once against real data on Windows; it fails immediately and
loudly on the first offending record.
